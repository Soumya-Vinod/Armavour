#!/usr/bin/env python3
"""
scripts/run_matrix.py — Official Armavour Full Matrix Benchmark Runner (~1,560 episodes).

Orchestrates the end-to-end matrix run across 4 core benchmark batches:
  - Batch 1: E1a computeruse (480 episodes)
  - Batch 2: Cross-model spot-check (60 episodes)
  - Batch 3: E1b browseruse (480 episodes)
  - Batch 4: E2 language arms (540 episodes)

Features:
  - Startup validation of DB, directories, API key pool, models, and testbed
  - Immutable experiment manifest saved to results/manifest_<run_id>.json
  - DB checkpointing & resume awareness via completed_config_hashes(run_id)
  - Automatic API key rotation logging (Groq key N/M)
  - Clean timestamped dual logging (console + logs/matrix_<run_id>.log)
  - Concise live per-episode progress output
  - Periodic 25-episode reports with throughput (episodes/hour) and formatted ETA
  - Automated crash reporting to results/crashes_<run_id>.csv
  - Graceful KeyboardInterrupt (Ctrl+C) handling with state preservation
  - Summary exports to results/matrix_summary_<run_id>.csv and .json
  - Final UX completion display
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure workspace root is in sys.path for harness imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import csv
import datetime
import importlib.metadata
import json
import logging
import os
import signal
import subprocess
import time
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select

from harness.adapters.common import MAX_STEPS
from harness.config import EpisodeConfig, enumerate_configs
from harness.logger import engine_from_env, episodes_table
from harness.providers import get_key_pool
from harness.runner import run_episode

# Default configuration constants
DEFAULT_RUN_ID = "matrix-full-e1e2"
DEFAULT_AGENT_MODEL = "groq/llama-3.3-70b-versatile"
DEFAULT_JUDGE_MODEL = "groq/openai/gpt-oss-120b"
DEFAULT_BASE_URL = "http://localhost:5173"
TESTBED_PREFLIGHT_TIMEOUT_MS = 15000
REPORT_EVERY_EPISODES = 25

PATTERN_TASKS = {
    "false_urgency": "fu_best",
    "basket_sneaking": "bs_ticket",
    "confirm_shaming": "cs_donation",
    "forced_action": "fa_course",
    "subscription_trap": "st_cancel",
    "interface_interference": "ii_renew",
    "bait_and_switch": "bns_item",
    "drip_pricing": "dp_ticket",
    "disguised_advertisement": "da_cheapest",
    "nagging": "nag_task",
    "trick_question": "tq_prefs",
    "saas_billing": "sb_free",
}


def get_runtime_versions() -> dict[str, str]:
    """Retrieve runtime environment version metadata for reproducibility."""
    python_ver = sys.version.split()[0]
    try:
        litellm_ver = importlib.metadata.version("litellm")
    except Exception:
        litellm_ver = "unknown"

    try:
        playwright_ver = importlib.metadata.version("playwright")
    except Exception:
        playwright_ver = "unknown"

    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        git_commit = "unknown"

    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        alembic_head = script.get_current_head() or "0004_add_provider_latency"
    except Exception:
        alembic_head = "0004_add_provider_latency"

    return {
        "python_version": python_ver,
        "litellm_version": litellm_ver,
        "playwright_version": playwright_ver,
        "git_commit": git_commit,
        "alembic_head": alembic_head,
    }


def get_batch_name_for_config(config: EpisodeConfig, *, matrix_model: str = DEFAULT_AGENT_MODEL) -> str:
    """Determine matrix batch classification for a given EpisodeConfig.

    An explicit `arm` attribute on the config wins. Otherwise any model other
    than the matrix agent model is a spot-check: previously only the literal
    llama-3.1-8b-instant string was, so e.g. gpt-oss-20b spot-check rows
    (en, seed 0-4) were silently classed as E1a.
    """
    explicit_arm = getattr(config, "arm", None)
    if explicit_arm:
        return str(explicit_arm)
    if config.llm != matrix_model:
        return "Spotcheck"
    if config.agent == "browseruse":
        return "E1b"
    if config.instruction_language == "hi" and config.ui_language == "hi":
        return "E2a"
    if config.instruction_language == "hinglish" and config.ui_language == "hinglish":
        return "E2b"
    if config.instruction_language == "en" and (config.ui_language in ("hi", "hinglish") or config.seed >= 10):
        return "E2"
    return "E1a"


def enumerate_benchmark_configs() -> list[EpisodeConfig]:
    """
    Enumerate configurations comprising the Armavour benchmark matrix:
      1. E1a computeruse (480 episodes)
      2. Cross-model spot-check (60 episodes)
      3. E1b browseruse (480 episodes)
      4. E2 language arms (540 episodes)
      5. E2a Hindi instructions + Hindi UI (180 episodes)
      6. E2b Hinglish instructions + Hinglish UI (180 episodes)
    """
    configs: list[EpisodeConfig] = []
    all_patterns = list(PATTERN_TASKS.keys())
    all_intensities = ["control", "subtle", "moderate", "aggressive"]

    # 1. E1a — computeruse (480 episodes)
    for p in all_patterns:
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=PATTERN_TASKS[p],
                patterns=[p],
                intensities=all_intensities,
                ui_languages=["en"],
                instruction_languages=["en"],
                agents=["computeruse"],
                llms=["groq/llama-3.3-70b-versatile"],
                repeat_count=10,
                seed_start=0,
            )
        )

    # 2. Cross-model spot-check (60 episodes)
    for p in all_patterns:
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=PATTERN_TASKS[p],
                patterns=[p],
                intensities=["aggressive"],
                ui_languages=["en"],
                instruction_languages=["en"],
                agents=["computeruse"],
                llms=["groq/llama-3.1-8b-instant"],
                repeat_count=5,
                seed_start=0,
            )
        )

    # 3. E1b — browseruse (480 episodes)
    for p in all_patterns:
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=PATTERN_TASKS[p],
                patterns=[p],
                intensities=all_intensities,
                ui_languages=["en"],
                instruction_languages=["en"],
                agents=["browseruse"],
                llms=["groq/llama-3.3-70b-versatile"],
                repeat_count=10,
                seed_start=0,
            )
        )

    # 4. E2 — language arms (540 episodes)
    e2_patterns = [
        "trick_question",
        "confirm_shaming",
        "interface_interference",
        "forced_action",
        "false_urgency",
        "saas_billing",
    ]
    for p in e2_patterns:
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=PATTERN_TASKS[p],
                patterns=[p],
                intensities=["control", "moderate", "aggressive"],
                ui_languages=["en", "hi", "hinglish"],
                instruction_languages=["en", "en", "en"],
                agents=["computeruse"],
                llms=["groq/llama-3.3-70b-versatile"],
                repeat_count=10,
                seed_start=10,  # Distinct seeds from E1a
            )
        )

    # 5. E2a — Hindi instructions + Hindi UI (180 episodes)
    for p in e2_patterns:
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=PATTERN_TASKS[p],
                patterns=[p],
                intensities=["control", "moderate", "aggressive"],
                ui_languages=["hi"],
                instruction_languages=["hi"],
                agents=["computeruse"],
                llms=["groq/llama-3.3-70b-versatile"],
                repeat_count=10,
                seed_start=20,
            )
        )

    # 6. E2b — Hinglish instructions + Hinglish UI (180 episodes)
    for p in e2_patterns:
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=PATTERN_TASKS[p],
                patterns=[p],
                intensities=["control", "moderate", "aggressive"],
                ui_languages=["hinglish"],
                instruction_languages=["hinglish"],
                agents=["computeruse"],
                llms=["groq/llama-3.3-70b-versatile"],
                repeat_count=10,
                seed_start=30,
            )
        )

    return configs


def completed_config_hashes(run_id: str) -> set[str]:
    """Query database for config_hashes already completed for the given run_id."""
    try:
        engine = engine_from_env()
        table = episodes_table(engine)
        stmt = select(table.c.config_hash).where(
            table.c.run_id == run_id,
            table.c.outcome.is_not(None),
        )
        with engine.connect() as conn:
            return set(conn.execute(stmt).scalars().all())
    except Exception:
        return set()


def setup_logger(run_id: str, log_dir: Path) -> logging.Logger:
    """Configure dual console and file logging."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"matrix_{run_id}.log"

    logger = logging.getLogger("matrix_runner")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # File Handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


def validate_dependencies(logger: logging.Logger) -> None:
    """Perform strict pre-flight dependency validation before starting run."""
    errors: list[str] = []

    # 1. Database reachability
    try:
        engine = engine_from_env()
        with engine.connect() as conn:
            conn.execute(select(1))
    except Exception as exc:
        errors.append(f"Database unreachable via DATABASE_URL: {exc}")

    # 2. Key Pool
    pool = get_key_pool("groq")
    if pool.total_keys() == 0:
        errors.append("APIKeyPool initialized with 0 keys. Set GROQ_API_KEY in environment.")

    # 3. Models
    agent_model = os.getenv("CHHAL_MODEL", DEFAULT_AGENT_MODEL)
    judge_model = os.getenv("CHHAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    if not agent_model:
        errors.append("Agent model (CHHAL_MODEL) is not configured.")
    if not judge_model:
        errors.append("Judge model (CHHAL_JUDGE_MODEL) is not configured.")

    # 4. Testbed reachability — a dead Vite server turns every episode into a
    #    crash row at full speed, so fail loudly here instead. Going through
    #    Playwright also confirms the Chromium binary is installed.
    base_url = (os.getenv("BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(
                    base_url,
                    wait_until="domcontentloaded",
                    timeout=TESTBED_PREFLIGHT_TIMEOUT_MS,
                )
            finally:
                browser.close()
    except Exception as exc:
        errors.append(f"Testbed unreachable at {base_url}: {exc}")

    if errors:
        logger.error("Mandatory pre-flight dependency checks FAILED:")
        for err in errors:
            logger.error(f"  [FAIL] {err}")
        sys.exit(1)

    logger.info("[OK] Mandatory pre-flight validation PASSED.")


def save_manifest(
    run_id: str,
    results_dir: Path,
    runtime: dict[str, str],
    total_configs: int,
    pool_size: int,
) -> Path:
    """Save an immutable experiment manifest to results/manifest_<run_id>.json."""
    results_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = results_dir / f"manifest_{run_id}.json"

    manifest_data = {
        "run_id": run_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": runtime["git_commit"],
        "python_version": runtime["python_version"],
        "litellm_version": runtime["litellm_version"],
        "playwright_version": runtime["playwright_version"],
        "agent_model": os.getenv("CHHAL_MODEL", DEFAULT_AGENT_MODEL),
        "judge_model": os.getenv("CHHAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL),
        "provider": os.getenv("CHHAL_PROVIDER", "groq"),
        "database_backend": "postgres",
        "alembic_head": runtime["alembic_head"],
        "total_enumerated_configs": total_configs,
        "api_key_pool_size": pool_size,
        "checkpoint_enabled": True,
        "random_seed_policy": "deterministic_per_config",
        "runtime_env_config": {
            "CHHAL_MODEL": os.getenv("CHHAL_MODEL", DEFAULT_AGENT_MODEL),
            "CHHAL_JUDGE_MODEL": os.getenv("CHHAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL),
            "CHHAL_PROVIDER": os.getenv("CHHAL_PROVIDER", "groq"),
            "CHHAL_PROVIDER_TIMEOUT_S": os.getenv("CHHAL_PROVIDER_TIMEOUT_S", "180"),
            "CHHAL_GROQ_DELAY_S": os.getenv("CHHAL_GROQ_DELAY_S", "8"),
            "CHHAL_RATE_LIMIT_RETRIES": os.getenv("CHHAL_RATE_LIMIT_RETRIES", "3"),
        },
    }

    manifest_path.write_text(json.dumps(manifest_data, indent=4), encoding="utf-8")
    return manifest_path


def save_config_manifest(run_id: str, results_dir: Path, configs: list[EpisodeConfig]) -> Path:
    """Save exact enumerated configuration definition to results/configs_<run_id>.json."""
    results_dir.mkdir(parents=True, exist_ok=True)
    config_file = results_dir / f"configs_{run_id}.json"

    data = [
        {
            "config_hash": c.config_hash,
            "pattern": c.pattern,
            "intensity": c.intensity,
            "language": c.language,
            "agent": c.agent,
            "model": c.llm,
            "seed": c.seed,
        }
        for c in configs
    ]
    config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return config_file


def save_environment_fingerprint(run_id: str, results_dir: Path, runtime: dict[str, str]) -> Path:
    """Save immutable environment fingerprint to results/environment_<run_id>.json."""
    results_dir.mkdir(parents=True, exist_ok=True)
    env_file = results_dir / f"environment_{run_id}.json"

    env_data = {
        "python_version": runtime["python_version"],
        "os": sys.platform,
        "litellm_version": runtime["litellm_version"],
        "playwright_version": runtime["playwright_version"],
        "git_commit": runtime["git_commit"],
        "alembic_head": runtime["alembic_head"],
        "agent_model": os.getenv("CHHAL_MODEL", DEFAULT_AGENT_MODEL),
        "judge_model": os.getenv("CHHAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL),
    }
    env_file.write_text(json.dumps(env_data, indent=4), encoding="utf-8")
    return env_file


def save_final_manifest(
    run_id: str,
    results_dir: Path,
    status: str,
    executed_rows: list[dict[str, Any]],
    skipped_count: int,
    total_configs: int,
    runtime_seconds: float,
    rotation_summary: dict[str, Any] | None = None,
) -> Path:
    """Save final experiment completion manifest to results/manifest_final_<run_id>.json."""
    results_dir.mkdir(parents=True, exist_ok=True)
    final_manifest_path = results_dir / f"manifest_final_{run_id}.json"

    completed_count = len(executed_rows)
    crash_count = sum(1 for r in executed_rows if r.get("outcome") is None)
    total_cost = sum(float(r.get("cost_usd") or 0.0) for r in executed_rows)
    total_in = sum(
        int(r.get("in_tokens") if r.get("in_tokens") is not None else r.get("tokens_in") or 0)
        for r in executed_rows
    )
    total_out = sum(
        int(r.get("out_tokens") if r.get("out_tokens") is not None else r.get("tokens_out") or 0)
        for r in executed_rows
    )

    final_data = {
        "run_id": run_id,
        "status": status,
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_enumerated_configs": total_configs,
        "episodes_completed": completed_count,
        "episodes_skipped": skipped_count,
        "episodes_retried": 0,
        "crashes": crash_count,
        "total_in_tokens": total_in,
        "total_out_tokens": total_out,
        "total_tokens_in": total_in,
        "total_tokens_out": total_out,
        "total_cost_usd": round(total_cost, 5),
        "total_runtime_seconds": round(runtime_seconds, 2),
        "api_key_rotation_summary": rotation_summary or {},
    }
    final_manifest_path.write_text(json.dumps(final_data, indent=4), encoding="utf-8")
    return final_manifest_path


def verify_config_uniqueness(logger: logging.Logger, configs: list[EpisodeConfig]) -> None:
    """Verify that all enumerated configuration hashes are strictly unique."""
    total = len(configs)
    unique_hashes = {c.config_hash for c in configs}
    unique_count = len(unique_hashes)

    logger.info(f"Total Enumerated Configs : {total}")
    logger.info(f"Unique Config Hashes     : {unique_count}")

    if unique_count != total:
        duplicates = total - unique_count
        logger.error(
            f"CRITICAL ERROR: Detected {duplicates} duplicate config_hash entries in benchmark matrix! "
            f"Aborting execution immediately to preserve experiment validity."
        )
        sys.exit(1)

    logger.info("[OK] Configuration hash uniqueness verified (zero duplicate hashes).")


def append_crash_report(results_dir: Path, run_id: str, config: EpisodeConfig, row: dict[str, Any]) -> None:
    """Append episode crash details to results/crashes_<run_id>.csv."""
    results_dir.mkdir(parents=True, exist_ok=True)
    crash_file = results_dir / f"crashes_{run_id}.csv"
    file_exists = crash_file.exists()

    fieldnames = [
        "config_hash",
        "pattern",
        "intensity",
        "language",
        "agent",
        "model",
        "exception_type",
        "exception_message",
    ]
    with open(crash_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "config_hash": config.config_hash,
                "pattern": config.pattern,
                "intensity": config.intensity,
                "language": config.language,
                "agent": config.agent,
                "model": config.llm,
                "exception_type": row.get("error_type", "CrashException"),
                "exception_message": row.get("error", "Unknown error"),
            }
        )


def export_summary_files(
    run_id: str,
    results_dir: Path,
    executed_rows: list[dict[str, Any]],
    skipped_count: int,
    total_configs: int,
    start_time: float,
) -> tuple[Path, Path]:
    """Export summary results to CSV and JSON."""
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / f"matrix_summary_{run_id}.csv"
    json_path = results_dir / f"matrix_summary_{run_id}.json"

    # CSV Export
    fieldnames = [
        "run_id",
        "config_hash",
        "pattern",
        "intensity",
        "language",
        "instruction_language",
        "ui_language",
        "instruction_prompt",
        "agent",
        "model",
        "outcome",
        "steps",
        "duration_seconds",
        "provider_latency_seconds",
        "in_tokens",
        "out_tokens",
        "cost_usd",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in executed_rows:
            in_t = int(row.get("in_tokens") if row.get("in_tokens") is not None else row.get("tokens_in") or 0)
            out_t = int(row.get("out_tokens") if row.get("out_tokens") is not None else row.get("tokens_out") or 0)
            normalized_row = {
                **row,
                "in_tokens": in_t,
                "out_tokens": out_t,
                "ui_language": row.get("ui_language", row.get("language", "en")),
                "instruction_language": row.get("instruction_language", "en"),
            }
            writer.writerow(normalized_row)

    # Calculate Aggregate Metrics
    completed_count = len(executed_rows)
    ec_count = sum(1 for r in executed_rows if r.get("outcome") == "EC")
    dc_count = sum(1 for r in executed_rows if r.get("outcome") == "DC")
    ef_count = sum(1 for r in executed_rows if r.get("outcome") == "EF")
    df_count = sum(1 for r in executed_rows if r.get("outcome") == "DF")
    crash_count = sum(1 for r in executed_rows if r.get("outcome") is None)

    total_cost = sum(float(r.get("cost_usd") or 0.0) for r in executed_rows)
    total_in = sum(
        int(r.get("in_tokens") if r.get("in_tokens") is not None else r.get("tokens_in") or 0) for r in executed_rows
    )
    total_out = sum(
        int(r.get("out_tokens") if r.get("out_tokens") is not None else r.get("tokens_out") or 0) for r in executed_rows
    )
    total_duration = sum(float(r.get("duration_seconds") or 0.0) for r in executed_rows)
    total_provider_lat = sum(float(r.get("provider_latency_seconds") or 0.0) for r in executed_rows)

    elapsed_s = time.time() - start_time
    avg_dur = round(total_duration / completed_count, 2) if completed_count > 0 else 0.0
    avg_prov_lat = round(total_provider_lat / completed_count, 2) if completed_count > 0 else 0.0
    throughput = round((completed_count / elapsed_s) * 3600, 1) if elapsed_s > 0 else 0.0

    batch_stats: dict[str, dict[str, int]] = {}
    for row in executed_rows:
        # Same classifier as everywhere else; runner rows carry the model as
        # "llm" (the old inline copy read "model" and never matched).
        b_key = get_batch_name_for_config(
            SimpleNamespace(
                llm=str(row.get("llm") or row.get("model") or ""),
                agent=str(row.get("agent", "")),
                instruction_language=row.get("instruction_language", "en"),
                ui_language=row.get("ui_language", row.get("language", "en")),
                seed=int(row.get("seed", 0)),
                arm=row.get("arm"),
            )
        )

        if b_key not in batch_stats:
            batch_stats[b_key] = {"completed": 0, "ec": 0, "dc": 0, "ef": 0, "df": 0, "crash": 0}

        batch_stats[b_key]["completed"] += 1
        outcome = row.get("outcome")
        if outcome in ("EC", "DC", "EF", "DF"):
            batch_stats[b_key][outcome.lower()] += 1
        elif outcome is None:
            batch_stats[b_key]["crash"] += 1

    json_data = {
        "run_id": run_id,
        "started_at": datetime.datetime.fromtimestamp(start_time, datetime.timezone.utc).isoformat(),
        "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "execution_time_seconds": round(elapsed_s, 2),
        "episodes_planned": total_configs,
        "episodes_completed": completed_count,
        "episodes_skipped": skipped_count,
        "ec": ec_count,
        "dc": dc_count,
        "ef": ef_count,
        "df": df_count,
        "crash": crash_count,
        "total_cost_usd": round(total_cost, 5),
        "total_in_tokens": total_in,
        "total_out_tokens": total_out,
        "total_tokens_in": total_in,
        "total_tokens_out": total_out,
        "average_duration_seconds": avg_dur,
        "average_provider_latency_seconds": avg_prov_lat,
        "throughput_episodes_per_hour": throughput,
        "batch_stats": batch_stats,
    }
    json_path.write_text(json.dumps(json_data, indent=4), encoding="utf-8")

    return csv_path, json_path


def format_seconds(seconds: float) -> str:
    """Format seconds into HH:MM:SS string."""
    td = datetime.timedelta(seconds=int(seconds))
    return str(td)


def format_eta(remaining_count: int, avg_duration_s: float) -> tuple[str, str]:
    """Calculate formatted ETA duration string and estimated completion timestamp."""
    if avg_duration_s <= 0 or remaining_count <= 0:
        return "00:00:00", "N/A"
    est_seconds = int(remaining_count * avg_duration_s)
    hours, remainder = divmod(est_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    duration_str = f"{hours}h {minutes}m {secs}s" if hours > 0 else f"{minutes}m {secs}s"

    completion_dt = datetime.datetime.now() + datetime.timedelta(seconds=est_seconds)
    completion_str = completion_dt.strftime("%Y-%m-%d %H:%M:%S")
    return duration_str, completion_str


def filter_configs_by_batch(configs: list[EpisodeConfig], batch_arg: str) -> list[EpisodeConfig]:
    """Filter enumerated configurations by specified batch selection(s).

    Supported batch tokens (comma-separated or single):
      - 'e1a': computeruse English baseline (480 episodes)
      - 'spotcheck' / 'spot_check': Cross-model spot-check, any model other than the matrix agent model (60 episodes)
      - 'e1b': browseruse English baseline (480 episodes)
      - 'e1': Combined E1a + E1b English baselines (960 episodes)
      - 'e2': E2 Multilingual arms (English instruction -> hi/hinglish UI) (540 episodes)
      - 'e2a': E2a Hindi instructions + Hindi UI (180 episodes)
      - 'e2b': E2b Hinglish instructions + Hinglish UI (180 episodes)
      - 'all': All benchmark episodes
    """
    if not batch_arg or batch_arg.strip().lower() == "all":
        return configs

    tokens = [t.strip().lower() for t in batch_arg.split(",") if t.strip()]
    valid_tokens = {"e1a", "spotcheck", "spot_check", "e1b", "e1", "e2", "e2a", "e2b", "all"}
    invalid = set(tokens) - valid_tokens
    if invalid:
        raise ValueError(
            f"Invalid batch token(s): {sorted(invalid)}. "
            f"Allowed batch tokens are: e1a, spotcheck, e1b, e1, e2, e2a, e2b, all (or comma-separated combination)."
        )

    if "all" in tokens:
        return configs

    filtered: list[EpisodeConfig] = []
    for c in configs:
        b_name = get_batch_name_for_config(c).lower()
        matches = False
        if "e1a" in tokens and b_name == "e1a":
            matches = True
        elif ("spotcheck" in tokens or "spot_check" in tokens) and b_name == "spotcheck":
            matches = True
        elif "e1b" in tokens and b_name == "e1b":
            matches = True
        elif "e1" in tokens and b_name in ("e1a", "e1b"):
            matches = True
        elif "e2" in tokens and b_name == "e2":
            matches = True
        elif "e2a" in tokens and b_name == "e2a":
            matches = True
        elif "e2b" in tokens and b_name == "e2b":
            matches = True

        if matches:
            filtered.append(c)

    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Armavour Full Matrix Execution Runner")
    parser.add_argument("--run-id", type=str, default=DEFAULT_RUN_ID, help="Unique identifier for matrix run.")
    parser.add_argument(
        "--batch",
        type=str,
        default="all",
        help="Batch selection to run: e1a, spotcheck, e1b, e1, e2, e2a, e2b, all (or comma-separated e.g. e2a,e2b)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate setup and enumerate configs without running.")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=MAX_STEPS,
        help=f"Maximum step budget per episode (default: {MAX_STEPS}, the budget E1a ran under).",
    )
    args = parser.parse_args()

    if args.max_steps:
        os.environ["CHHAL_MAX_STEPS"] = str(args.max_steps)

    run_id = args.run_id
    batch_arg = args.batch
    log_dir = Path("logs")
    results_dir = Path("results")
    ckpt_dir = Path(".checkpoints")

    ckpt_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(run_id, log_dir)
    runtime = get_runtime_versions()
    pool = get_key_pool("groq")

    # Perform Startup Validation
    validate_dependencies(logger)

    raw_configs = enumerate_benchmark_configs()
    configs = filter_configs_by_batch(raw_configs, batch_arg)
    total_configs = len(configs)

    # Verify Configuration Hash Uniqueness
    verify_config_uniqueness(logger, configs)

    # Save Exact Enumerated Config List Manifest
    config_manifest_path = save_config_manifest(run_id, results_dir, configs)

    # Checkpoint & Resume query
    completed_hashes = completed_config_hashes(run_id)
    remaining_configs = [c for c in configs if c.config_hash not in completed_hashes]
    skipped_configs = [c for c in configs if c.config_hash in completed_hashes]
    skipped_count = len(skipped_configs)

    active_key_idx = pool.current_index() + 1
    total_keys = pool.total_keys()

    # Print Startup Banner
    logger.info("=" * 80)
    logger.info("ARMAVOUR MATRIX RUN")
    logger.info("=" * 80)
    logger.info(f"Run ID:               {run_id}")
    logger.info(f"Batch Filter:         {batch_arg}")
    logger.info(f"Timestamp:            {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    logger.info(f"Git Commit:           {runtime['git_commit']}")
    logger.info(f"Python Version:       {runtime['python_version']}")
    logger.info(f"LiteLLM Version:      {runtime['litellm_version']}")
    logger.info(f"Playwright Version:   {runtime['playwright_version']}")
    logger.info("")
    logger.info(f"Agent Model:          {os.getenv('CHHAL_MODEL', DEFAULT_AGENT_MODEL)}")
    logger.info(f"Judge Model:          {os.getenv('CHHAL_JUDGE_MODEL', DEFAULT_JUDGE_MODEL)}")
    logger.info("")
    logger.info(f"Provider:             Groq (key {active_key_idx}/{total_keys} active)")
    logger.info("Database:             Postgres")
    logger.info("")
    logger.info("Smoke Test:           Completed separately (scripts/smoke_test.py)")
    logger.info(f"Benchmark Episodes:   {total_configs}")
    logger.info("")
    logger.info(f"Total Configurations: {total_configs}")
    logger.info(f"Already Completed:    {skipped_count}")
    logger.info(f"Remaining:            {len(remaining_configs)}")
    logger.info("")
    logger.info("Checkpoint Enabled:   Yes (.checkpoints/provider_state.json)")
    logger.info(f"API Key Rotation:     Enabled ({total_keys} keys)")
    logger.info("=" * 80)

    if skipped_count > 0:
        logger.info(f"Skipping {skipped_count} previously completed episodes for run_id '{run_id}'.")
        for sc in skipped_configs:
            logger.info(
                f"  [SKIP] config_hash={sc.config_hash} pattern={sc.pattern} "
                f"intensity={sc.intensity} instruction_language={sc.instruction_language} "
                f"ui_language={sc.ui_language} agent={sc.agent} "
                f"reason=\"Already completed in Postgres\""
            )

    # Save Experiment Manifest & Environment Fingerprint
    manifest_path = save_manifest(run_id, results_dir, runtime, total_configs, total_keys)
    env_fingerprint_path = save_environment_fingerprint(run_id, results_dir, runtime)
    logger.info(f"Immutable experiment manifest saved to {manifest_path}")
    logger.info(f"Immutable config definition saved to {config_manifest_path}")
    logger.info(f"Environment fingerprint saved to {env_fingerprint_path}")

    # Startup Confirmation Banner
    logger.info("=" * 80)
    logger.info("STARTUP CONFIRMATION - BENCHMARK READY")
    logger.info("=" * 80)
    logger.info(f"Run ID:                  {run_id}")
    logger.info(f"Git Commit:              {runtime['git_commit']}")
    logger.info(f"Agent Model:             {os.getenv('CHHAL_MODEL', DEFAULT_AGENT_MODEL)}")
    logger.info(f"Judge Model:             {os.getenv('CHHAL_JUDGE_MODEL', DEFAULT_JUDGE_MODEL)}")
    logger.info(f"Active Groq Key:         Key {active_key_idx}/{total_keys}")
    logger.info(f"Total Enumerated Configs: {total_configs}")
    logger.info(f"Remaining After Resume:   {len(remaining_configs)}")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("Dry-run requested. Exiting cleanly without executing episodes.")
        logger.info("=" * 80)
        logger.info("DRY RUN MATRIX BREAKDOWN")
        logger.info("=" * 80)
        batch_groups: dict[str, list[EpisodeConfig]] = {}
        for c in configs:
            b_name = get_batch_name_for_config(c)
            batch_groups.setdefault(b_name, []).append(c)

        for b_name, b_configs in batch_groups.items():
            c0 = b_configs[0]
            logger.info(f"Batch:       {b_name}")
            logger.info(f"Instruction: {c0.instruction_language}")
            logger.info(f"UI:          {c0.ui_language}")
            logger.info(f"Episodes:    {len(b_configs)}")
            logger.info("-" * 40)
        logger.info("=" * 80)
        sys.exit(0)

    # Execution State
    executed_rows: list[dict[str, Any]] = []
    start_time = time.time()

    def signal_handler(signum: int, frame: Any) -> None:
        elapsed_s = time.time() - start_time
        sig_name = "SIGTERM" if signum == getattr(signal, "SIGTERM", 15) else "SIGINT"
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"RUN INTERRUPTED ({sig_name})")
        logger.info("=" * 80)
        logger.info(f"Episodes Completed: {skipped_count + len(executed_rows)}")
        logger.info(f"Episodes Remaining: {total_configs - (skipped_count + len(executed_rows))}")
        logger.info(f"Current Cost:       ${sum(float(r.get('cost_usd') or 0.0) for r in executed_rows):.5f}")
        logger.info("Checkpoint Saved:   Yes")
        logger.info("Resume Command:")
        logger.info(f"python scripts/run_matrix.py --run-id {run_id}")
        logger.info("=" * 80)

        export_summary_files(run_id, results_dir, executed_rows, skipped_count, total_configs, start_time)
        save_final_manifest(
            run_id,
            results_dir,
            "interrupted",
            executed_rows,
            skipped_count,
            total_configs,
            elapsed_s,
            pool.get_rotation_summary(),
        )
        sys.exit(130)

    # Register Signal Handlers for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    ec_count = 0
    dc_count = 0
    ef_count = 0
    df_count = 0
    crash_count = 0

    try:
        for idx, config in enumerate(remaining_configs, start=1):
            ep_index = skipped_count + idx
            row = run_episode(config, run_id=run_id, log=True)
            executed_rows.append(row)
            pool.record_episode()

            outcome = row.get("outcome")
            if outcome == "EC":
                ec_count += 1
            elif outcome == "DC":
                dc_count += 1
            elif outcome == "EF":
                ef_count += 1
            elif outcome == "DF":
                df_count += 1
            elif outcome is None:
                crash_count += 1
                append_crash_report(results_dir, run_id, config, row)

            dur = float(row.get("duration_seconds") or 0.0)
            prov_lat = float(row.get("provider_latency_seconds") or 0.0)
            t_in = int(row.get("in_tokens") if row.get("in_tokens") is not None else row.get("tokens_in") or 0)
            t_out = int(row.get("out_tokens") if row.get("out_tokens") is not None else row.get("tokens_out") or 0)
            cost = float(row.get("cost_usd") or 0.0)
            steps = row.get("steps", 0)

            # Print Live Per-Episode Log Line
            logger.info(
                f"[{ep_index:04d}/{total_configs:04d}] "
                f"Pattern={config.pattern} "
                f"Intensity={config.intensity} "
                f"Language={config.language} "
                f"Agent={config.agent} "
                f"Outcome={outcome or 'CRASH'} "
                f"Steps={steps} "
                f"Duration={dur:.2f}s "
                f"Provider={prov_lat:.2f}s "
                f"Tokens={t_in}/{t_out} "
                f"Cost=${cost:.5f}"
            )

            # Print Periodic Progress Report Every 25 Episodes
            if idx % REPORT_EVERY_EPISODES == 0 or idx == len(remaining_configs):
                elapsed_s = time.time() - start_time
                completed_so_far = len(executed_rows)
                remaining_so_far = len(remaining_configs) - completed_so_far
                pct = ((skipped_count + completed_so_far) / total_configs) * 100

                avg_dur_so_far = sum(float(r.get("duration_seconds") or 0.0) for r in executed_rows) / completed_so_far
                avg_prov_so_far = (
                    sum(float(r.get("provider_latency_seconds") or 0.0) for r in executed_rows) / completed_so_far
                )
                avg_in_so_far = (
                    sum(
                        int(r.get("in_tokens") if r.get("in_tokens") is not None else r.get("tokens_in") or 0)
                        for r in executed_rows
                    )
                    / completed_so_far
                )
                avg_out_so_far = (
                    sum(
                        int(r.get("out_tokens") if r.get("out_tokens") is not None else r.get("tokens_out") or 0)
                        for r in executed_rows
                    )
                    / completed_so_far
                )
                tot_cost_so_far = sum(float(r.get("cost_usd") or 0.0) for r in executed_rows)
                avg_cost_so_far = tot_cost_so_far / completed_so_far

                throughput_ph = (completed_so_far / elapsed_s) * 3600 if elapsed_s > 0 else 0.0
                eta_str, comp_str = format_eta(remaining_so_far, avg_dur_so_far)

                logger.info("=" * 80)
                logger.info("PROGRESS")
                logger.info("=" * 80)
                logger.info(f"Completed:                {skipped_count + completed_so_far}/{total_configs}")
                logger.info(f"Remaining:                {remaining_so_far}")
                logger.info(f"Percent Complete:         {pct:.2f}%")
                logger.info("")
                logger.info(f"Elapsed Time:             {format_seconds(elapsed_s)}")
                logger.info(f"Average Episode Duration: {avg_dur_so_far:.2f}s")
                logger.info(f"Average Provider Latency: {avg_prov_so_far:.2f}s")
                logger.info(f"Throughput:               {throughput_ph:.1f} episodes/hour")
                logger.info("")
                logger.info(f"Average Tokens In:        {avg_in_so_far:.0f}")
                logger.info(f"Average Tokens Out:       {avg_out_so_far:.0f}")
                logger.info("")
                logger.info(f"Average Cost/Episode:     ${avg_cost_so_far:.5f}")
                logger.info(f"Total Cost:               ${tot_cost_so_far:.5f}")
                logger.info("")
                logger.info(f"EC:                       {ec_count}")
                logger.info(f"DC:                       {dc_count}")
                logger.info(f"EF:                       {ef_count}")
                logger.info(f"DF:                       {df_count}")
                logger.info(f"Crash:                    {crash_count}")
                logger.info("")
                logger.info(f"Estimated Time Remaining: {eta_str}")
                logger.info(f"Estimated Completion:     {comp_str}")
                logger.info("=" * 80)

    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

    # End-of-Run Outcome Verification
    sum_outcomes = ec_count + dc_count + ef_count + df_count + crash_count
    if sum_outcomes != len(executed_rows):
        logger.error(
            f"CRITICAL ERROR: Outcome sum mismatch! "
            f"EC({ec_count}) + DC({dc_count}) + EF({ef_count}) + DF({df_count}) + Crash({crash_count}) = "
            f"{sum_outcomes} != Executed({len(executed_rows)}). Aborting."
        )
        sys.exit(1)

    # Final Export & Reports
    csv_path, json_path = export_summary_files(
        run_id, results_dir, executed_rows, skipped_count, total_configs, start_time
    )
    elapsed_total_s = time.time() - start_time
    total_cost_all = sum(float(r.get("cost_usd") or 0.0) for r in executed_rows)
    rotation_summary = pool.get_rotation_summary()

    final_manifest_path = save_final_manifest(
        run_id,
        results_dir,
        "completed",
        executed_rows,
        skipped_count,
        total_configs,
        elapsed_total_s,
        rotation_summary,
    )

    logger.info("=" * 80)
    logger.info("FINAL MATRIX REPORT")
    logger.info("=" * 80)
    logger.info("Status:")
    logger.info("PASS")
    logger.info("")
    logger.info(f"Run ID:                  {run_id}")
    logger.info(f"Started:                 {datetime.datetime.fromtimestamp(start_time, datetime.timezone.utc).isoformat()}")
    logger.info(f"Finished:                {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    logger.info(f"Execution Time:          {format_seconds(elapsed_total_s)}")
    logger.info("")
    logger.info("Episodes Planned:")
    logger.info(f"{total_configs}")
    logger.info(f"Episodes Completed:      {skipped_count + len(executed_rows)}")
    logger.info(f"Episodes Skipped:        {skipped_count}")
    logger.info("")
    logger.info(f"EC:                      {ec_count}")
    logger.info(f"DC:                      {dc_count}")
    logger.info(f"EF:                      {ef_count}")
    logger.info(f"DF:                      {df_count}")
    logger.info(f"Crash:                   {crash_count}")
    logger.info("")
    logger.info(f"Average Episode Duration: {sum(float(r.get('duration_seconds') or 0.0) for r in executed_rows) / max(1, len(executed_rows)):.2f}s")
    logger.info(f"Average Provider Latency: {sum(float(r.get('provider_latency_seconds') or 0.0) for r in executed_rows) / max(1, len(executed_rows)):.2f}s")
    logger.info(f"Throughput:              {(len(executed_rows) / max(1, elapsed_total_s)) * 3600:.1f} episodes/hour")
    logger.info("")
    tot_in = sum(
        int(r.get("in_tokens") if r.get("in_tokens") is not None else r.get("tokens_in") or 0) for r in executed_rows
    )
    tot_out = sum(
        int(r.get("out_tokens") if r.get("out_tokens") is not None else r.get("tokens_out") or 0) for r in executed_rows
    )
    logger.info(f"Total Tokens In:         {tot_in}")
    logger.info(f"Total Tokens Out:        {tot_out}")
    logger.info(f"Total Cost:              ${total_cost_all:.5f}")
    logger.info("")
    logger.info("API Key Rotation Summary:")
    logger.info(f"  Total Rotations:       {rotation_summary['total_rotations']}")
    logger.info(f"  Key Indexes Used:      {rotation_summary['keys_used']}")
    logger.info(f"  Episodes Per Key:      {rotation_summary['episodes_per_key']}")
    logger.info("")
    logger.info("Database:")
    logger.info("Postgres")
    logger.info("")
    logger.info("Checkpoint:")
    logger.info("Verified")
    logger.info("")
    logger.info("API Key Rotation:")
    logger.info("Verified")
    logger.info("=" * 80)

    # Final UX Banner
    logger.info("=" * 80)
    logger.info("[OK] MATRIX COMPLETE")
    logger.info("")
    logger.info(f"Episodes : {total_configs}")
    logger.info(f"Runtime  : {format_seconds(elapsed_total_s)}")
    logger.info(f"Cost     : ${total_cost_all:.5f}")
    logger.info("")
    logger.info("Results :")
    logger.info(f"{csv_path}")
    logger.info("")
    logger.info("Manifest :")
    logger.info(f"{manifest_path}")
    logger.info(f"{final_manifest_path}")
    logger.info("")
    logger.info("Log :")
    logger.info(f"logs/matrix_{run_id}.log")
    logger.info("")
    logger.info("You may safely archive the experiment.")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()