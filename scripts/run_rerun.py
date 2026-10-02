#!/usr/bin/env python3
"""
scripts/run_rerun.py - corrected rerun, baseline vs fixed testbed (RERUN_PREREG.md).

Every config runs on both testbed variants back to back, so drift over the run
(provider load, time of day) hits both variants alike:

  variant   BASE_URL                run_id
  baseline  http://localhost:5174   rerun-baseline-t07-01   frozen pre-fix copy (armavour_data/testbed_baseline)
  fixed     http://localhost:5173   rerun-fixed-t07-01      working testbed/ with docs/audit/FIXES.md

Within a pair the variant that goes first alternates with the config index, so
neither variant systematically runs second.

Common settings:
  agent        computeruse, groq/qwen/qwen3.8-27b, thinking suppressed exactly as in
               the leak ablation (harness/adapters/computeruse.py QWEN_REASONING_FALLBACKS)
  temperature  0.7 (CHHAL_TEMPERATURE; opt-in, default 0 elsewhere)
  steps        20
  config leak  OFF; the prompt guard from scripts/run_leak_ablation.py must pass
  judge        groq/openai/gpt-oss-120b (confirm_shaming)
  cells        10 scored patterns x 4 intensities x seeds 0-9, English UI + instruction
               = 400 configs per variant, 800 episodes

Refuses to start unless:
  - DATABASE_URL names armavour_rerun and the engine is connected to it, with
    migration 0007 applied;
  - git is available and the working tree has no uncommitted changes to tracked
    files (git status --porcelain --untracked-files=no is empty), so every row's
    code_sha is a clean commit; the code_sha is re-checked around every episode
    and the run stops if it changes;
  - both dev servers answer, and each port serves the variant it should (the
    fixed page renders the Free plan, the baseline does not).

--smoke writes to smoke-rerun-01-<variant> instead of the pre-registered run_ids
(one run_id per variant, because logger.py upserts on (config_hash, run_id) and
the variant is not part of config_hash). --allow-dirty skips the dirty-tree check
and is accepted only together with --smoke; the full run can never use it.

Resumable: a (config, variant) already stored with a non-NULL outcome is
skipped; crash rows are retried; logger.py upserts on (config_hash, run_id).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import datetime
import os
import signal
import subprocess
import time
import urllib.request
from typing import Any
from urllib.parse import urlencode, urlparse

from harness.adapters.computeruse import CONFIG_LEAK_ENV, TEMPERATURE_ENV, _is_qwen_model, sampling_temperature
from harness.config import EpisodeConfig, enumerate_configs
from harness.providers import get_key_pool
from harness.runner import REPO_ROOT, code_sha, run_episode
from scripts.run_leak_ablation import assert_prompt_has_no_config
from scripts.run_matrix import (
    PATTERN_TASKS,
    append_crash_report,
    export_summary_files,
    format_eta,
    format_seconds,
    get_runtime_versions,
    save_config_manifest,
    save_environment_fingerprint,
    save_final_manifest,
    save_manifest,
    setup_logger,
    validate_dependencies,
    verify_config_uniqueness,
)

AGENT_MODEL = "groq/qwen/qwen3.8-27b"
JUDGE_MODEL = "groq/openai/gpt-oss-120b"
TEMPERATURE = 0.7
MAX_STEPS = 20
DATABASE_NAME = "armavour_rerun"
EXCLUDED_PATTERNS = {"disguised_advertisement", "false_urgency"}
INTENSITIES = ["control", "subtle", "moderate", "aggressive"]
SEEDS = 10
VARIANTS: dict[str, dict[str, str]] = {
    "baseline": {"base_url": "http://localhost:5174", "run_id": "rerun-baseline-t07-01"},
    "fixed": {"base_url": "http://localhost:5173", "run_id": "rerun-fixed-t07-01"},
}
SMOKE_RUN_ID = "smoke-rerun-01"
NEW_COLUMNS = ("oracle_result", "testbed_variant", "terminal_reason")
REPORT_EVERY = 20


def enumerate_rerun_configs() -> list[EpisodeConfig]:
    configs: list[EpisodeConfig] = []
    for pattern, task_id in PATTERN_TASKS.items():
        if pattern in EXCLUDED_PATTERNS:
            continue
        configs.extend(
            enumerate_configs(
                site="ticketing", task_id=task_id, patterns=[pattern], intensities=INTENSITIES,
                ui_languages=["en"], instruction_languages=["en"], agents=["computeruse"],
                llms=[AGENT_MODEL], repeat_count=SEEDS, seed_start=0,
            )
        )
    return configs


def episode_order(configs: list[EpisodeConfig]) -> list[tuple[EpisodeConfig, str]]:
    """Each config on both variants back to back; the first variant alternates."""
    order: list[tuple[EpisodeConfig, str]] = []
    for i, config in enumerate(configs):
        pair = ("baseline", "fixed") if i % 2 == 0 else ("fixed", "baseline")
        order.extend((config, variant) for variant in pair)
    return order


def select_configs(configs: list[EpisodeConfig], only: list[str]) -> list[EpisodeConfig]:
    """--only pattern[:intensity[:seed]] filters (smoke tests)."""
    if not only:
        return configs
    keep = []
    for config in configs:
        for spec in only:
            parts = spec.split(":")
            if parts[0] != config.pattern:
                continue
            if len(parts) > 1 and parts[1] and parts[1] != config.intensity:
                continue
            if len(parts) > 2 and parts[2] and int(parts[2]) != config.seed:
                continue
            keep.append(config)
            break
    return keep


# ---- guards -----------------------------------------------------------------


def database_name(url: str) -> str:
    return urlparse(url.replace("postgresql+psycopg", "postgresql", 1)).path.lstrip("/")


def require_rerun_database() -> None:
    url = os.getenv("DATABASE_URL", "")
    name = database_name(url)
    if name != DATABASE_NAME:
        raise SystemExit(f"Refusing to start: DATABASE_URL names database {name!r}; the rerun writes only to {DATABASE_NAME!r}.")


def require_connected_database(engine: Any = None) -> None:
    """The engine the logger writes through is really connected to armavour_rerun."""
    from sqlalchemy import text

    from harness.logger import engine_from_env

    engine = engine or engine_from_env()
    with engine.connect() as conn:
        name = conn.execute(text("SELECT current_database()")).scalar()
    if name != DATABASE_NAME:
        raise SystemExit(f"Refusing to start: connected to database {name!r}, not {DATABASE_NAME!r}.")


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.STDOUT, timeout=30
    ).strip()


def require_git() -> str:
    """git must work: without it code_sha() silently falls back to ARMAVOUR_CODE_SHA or None."""
    try:
        _git("--version")
        return _git("rev-parse", "HEAD")
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Refusing to start: git is unavailable ({exc}); rows would carry no code_sha.") from exc


def require_clean_tree(allow_dirty: bool = False) -> list[str]:
    """Uncommitted changes to tracked files make code_sha '<sha>-dirty'; refuse unless allow_dirty."""
    dirty = [line for line in _git("status", "--porcelain", "--untracked-files=no").splitlines() if line.strip()]
    if dirty and not allow_dirty:
        listing = "\n  ".join(dirty)
        raise SystemExit(
            "Refusing to start: the working tree has uncommitted changes to tracked files; commit them first "
            f"so every row's code_sha is a clean commit:\n  {listing}"
        )
    return dirty


def require_code_sha(expected: str | None) -> None:
    """Stop if the commit or the tree state changed since the run started."""
    current = code_sha()
    if current != expected:
        raise SystemExit(
            f"Stopping: code_sha changed from {expected!r} to {current!r} during the run "
            "(new commit, edited tracked file, or git unavailable). Restore the tree, then rerun to resume."
        )


def completed_hashes(run_id: str, engine: Any = None) -> set[str]:
    """Config hashes stored with a non-NULL outcome.

    Unlike run_matrix.completed_config_hashes this does not swallow database
    errors: an empty set would make the run redo, and upsert over, completed rows.
    """
    from sqlalchemy import select

    from harness.logger import engine_from_env, episodes_table

    engine = engine or engine_from_env()
    table = episodes_table(engine)
    stmt = select(table.c.config_hash).where(table.c.run_id == run_id, table.c.outcome.is_not(None))
    with engine.connect() as conn:
        return set(conn.execute(stmt).scalars().all())


def require_schema(engine: Any = None) -> None:
    from harness.logger import engine_from_env, episodes_table

    engine = engine or engine_from_env()
    columns = {c.name for c in episodes_table(engine).columns}
    missing = [c for c in NEW_COLUMNS if c not in columns]
    if missing:
        raise SystemExit(f"Refusing to start: episodes lacks {missing}; apply migrations through 0007 to {DATABASE_NAME}.")


def refuse_mixed_models(engine: Any = None) -> None:
    from sqlalchemy import select

    from harness.logger import engine_from_env, episodes_table

    engine = engine or engine_from_env()
    table = episodes_table(engine)
    run_ids = [v["run_id"] for v in VARIANTS.values()]
    stmt = select(table.c.run_id, table.c.llm).where(table.c.run_id.in_(run_ids)).distinct()
    with engine.connect() as conn:
        found = [(r, m) for r, m in conn.execute(stmt).all() if m != AGENT_MODEL]
    if found:
        raise SystemExit(f"Refusing to start: rerun run_ids already hold rows from another model: {found}")


def _probe_url(base_url: str) -> str:
    params = {"site": "ticketing", "task_id": "sb_free", "pattern": "saas_billing", "intensity": "control", "lang": "en", "seed": 0}
    return f"{base_url}/?{urlencode(params)}"


def require_servers() -> None:
    """Both ports answer, and each serves its own variant (behavioural check, no testbed marker needed)."""
    for name, variant in VARIANTS.items():
        try:
            with urllib.request.urlopen(variant["base_url"], timeout=5) as resp:  # noqa: S310 - fixed localhost URLs
                if resp.status != 200:
                    raise OSError(f"HTTP {resp.status}")
        except OSError as exc:
            raise SystemExit(f"Refusing to start: {name} testbed at {variant['base_url']} is down ({exc}).") from exc
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for name, variant in VARIANTS.items():
                page = browser.new_page()
                page.goto(_probe_url(variant["base_url"]), wait_until="networkidle")
                has_free_plan = page.locator("#sb-free").count() > 0
                page.close()
                if has_free_plan != (name == "fixed"):
                    raise SystemExit(
                        f"Refusing to start: {variant['base_url']} does not serve the {name} variant "
                        f"(Free plan {'present' if has_free_plan else 'absent'}). Are the ports swapped?"
                    )
        finally:
            browser.close()


def configure_environment() -> None:
    os.environ["CHHAL_MODEL"] = AGENT_MODEL
    os.environ["CHHAL_JUDGE_MODEL"] = JUDGE_MODEL
    os.environ["CHHAL_MAX_STEPS"] = str(MAX_STEPS)
    os.environ[TEMPERATURE_ENV] = str(TEMPERATURE)
    os.environ.pop(CONFIG_LEAK_ENV, None)  # config leak OFF, whatever the shell says
    assert sampling_temperature() == TEMPERATURE
    assert _is_qwen_model(AGENT_MODEL), "thinking suppression only applies to qwen models"


def use_smoke_run_ids() -> None:
    """Smoke-test rows never share a run_id with the pre-registered data."""
    for name, variant in VARIANTS.items():
        variant["run_id"] = f"{SMOKE_RUN_ID}-{name}"


def use_variant(name: str) -> str:
    os.environ["BASE_URL"] = VARIANTS[name]["base_url"]
    os.environ["ARMAVOUR_TESTBED_VARIANT"] = name
    return VARIANTS[name]["run_id"]


# ---- main -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Corrected rerun: baseline vs fixed testbed (800 episodes)")
    parser.add_argument("--dry-run", action="store_true", help="Run every guard and enumerate episodes, then exit.")
    parser.add_argument("--only", action="append", default=[], metavar="PATTERN[:INTENSITY[:SEED]]",
                        help="Restrict to matching configs (smoke tests). Repeatable.")
    parser.add_argument("--max-episodes", type=int, default=None, help="Stop after this many episodes (smoke tests).")
    parser.add_argument("--smoke", action="store_true",
                        help=f"Write to {SMOKE_RUN_ID}-<variant> instead of the pre-registered run_ids.")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Smoke test only: skip the dirty-tree check. Rejected without --smoke.")
    args = parser.parse_args(argv)
    if args.allow_dirty and not args.smoke:
        parser.error("--allow-dirty is only for the smoke test (--smoke); the full rerun must run from a clean commit")
    if args.smoke:
        use_smoke_run_ids()

    configure_environment()
    require_rerun_database()
    head = require_git()
    dirty = require_clean_tree(allow_dirty=args.allow_dirty)
    start_sha = code_sha()
    if not dirty and start_sha != head:
        raise SystemExit(f"Refusing to start: code_sha() returned {start_sha!r}, expected the clean commit {head!r}.")
    assert_prompt_has_no_config(AGENT_MODEL)

    results_dir = Path("results") / "rerun"
    results_dir.mkdir(parents=True, exist_ok=True)
    Path(".checkpoints").mkdir(parents=True, exist_ok=True)
    logger = setup_logger(SMOKE_RUN_ID if args.smoke else "rerun-t07-01", Path("logs"))
    runtime = get_runtime_versions()
    pool = get_key_pool("groq")

    validate_dependencies(logger)
    require_connected_database()
    require_schema()
    refuse_mixed_models()
    require_servers()

    all_configs = enumerate_rerun_configs()
    verify_config_uniqueness(logger, all_configs)
    configs = select_configs(all_configs, args.only)
    if not configs:
        raise SystemExit(f"--only {args.only} matches no config")

    done = {name: completed_hashes(v["run_id"]) for name, v in VARIANTS.items()}
    plan = [(c, v) for c, v in episode_order(configs) if c.config_hash not in done[v]]
    if args.max_episodes is not None:
        plan = plan[: args.max_episodes]
    total = 2 * len(configs)
    skipped = total - len([1 for c, v in episode_order(configs) if c.config_hash not in done[v]])

    for name, variant in VARIANTS.items():
        save_config_manifest(variant["run_id"], results_dir, configs)
        save_manifest(variant["run_id"], results_dir, runtime, len(configs), pool.total_keys())
        save_environment_fingerprint(variant["run_id"], results_dir, runtime)

    logger.info("=" * 80)
    logger.info("ARMAVOUR CORRECTED RERUN (baseline vs fixed)")
    logger.info("=" * 80)
    logger.info(f"Timestamp:      {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    logger.info(f"Code SHA:       {start_sha}")
    if dirty:
        logger.info(f"WARNING:        --allow-dirty (smoke only): {len(dirty)} tracked file(s) uncommitted, rows carry a -dirty code_sha")
    logger.info(f"Agent / judge:  {AGENT_MODEL} / {JUDGE_MODEL}")
    logger.info(f"Temperature:    {TEMPERATURE}   Max steps: {MAX_STEPS}   Config leak: OFF (guard passed)")
    for name, variant in VARIANTS.items():
        logger.info(f"Variant {name:<8} {variant['base_url']}  run_id {variant['run_id']}  done {len(done[name] & {c.config_hash for c in configs})}")
    logger.info(f"Episodes:       {total} planned, {skipped} already stored, {len(plan)} to run now")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("Dry run: all guards passed. Exiting without running episodes.")
        return

    executed: dict[str, list[dict[str, Any]]] = {name: [] for name in VARIANTS}
    start = time.time()

    def finish(status: str) -> None:
        elapsed = time.time() - start
        for name, variant in VARIANTS.items():
            export_summary_files(variant["run_id"], results_dir, executed[name], len(done[name]), len(configs), start)
            save_final_manifest(variant["run_id"], results_dir, status, executed[name], len(done[name]), len(configs),
                                elapsed, pool.get_rotation_summary())

    def on_signal(signum: int, frame: Any) -> None:
        logger.info(f"INTERRUPTED after {sum(len(v) for v in executed.values())} episodes; rerun the same command to resume.")
        finish("interrupted")
        sys.exit(130)

    signal.signal(signal.SIGINT, on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_signal)

    try:
        for idx, (config, variant) in enumerate(plan, start=1):
            require_code_sha(start_sha)
            run_id = use_variant(variant)
            row = run_episode(config, run_id=run_id, log=True)
            if row.get("code_sha") != start_sha:
                raise SystemExit(
                    f"Stopping: row {run_id}/{config.config_hash} was stored with code_sha {row.get('code_sha')!r}, "
                    f"expected {start_sha!r}. Delete that row, restore the tree, then rerun to resume."
                )
            executed[variant].append(row)
            pool.record_episode()
            if row.get("outcome") is None:
                append_crash_report(results_dir, run_id, config, row)
            logger.info(
                f"[{skipped + idx:03d}/{total:03d}] {variant:<8} {config.pattern} {config.intensity} seed={config.seed} "
                f"v1={row.get('outcome') or 'CRASH'} end={row.get('terminal_reason')} steps={row.get('steps', 0)} "
                f"{float(row.get('duration_seconds') or 0.0):.1f}s"
            )
            if idx % REPORT_EVERY == 0 or idx == len(plan):
                rows = [r for v in executed.values() for r in v]
                avg = sum(float(r.get("duration_seconds") or 0.0) for r in rows) / len(rows)
                eta, _ = format_eta(len(plan) - idx, avg)
                logger.info(f"PROGRESS {skipped + idx}/{total} | elapsed {format_seconds(time.time() - start)} | ETA {eta}")
    except KeyboardInterrupt:
        # Includes TPDExhaustedError (all keys out of daily tokens): state is kept; rerun to resume.
        on_signal(signal.SIGINT, None)

    finish("completed" if args.max_episodes is None and not args.only else "partial")
    logger.info("[OK] rerun batch finished. Next: python scripts/analyze_rerun.py")


if __name__ == "__main__":
    main()
