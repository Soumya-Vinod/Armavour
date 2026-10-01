#!/usr/bin/env python3
"""
scripts/run_spotcheck.py — Armavour Cross-Model Spot-Check Benchmark Runner (60 episodes).

Runs the 60-episode cross-model spot-check benchmark suite using the model specified
in the `CHHAL_MODEL` environment variable (e.g., groq/openai/gpt-oss-20b), without
modifying existing spot-check records in the database.

Features:
  - Dynamic model resolution via CHHAL_MODEL (never hardcoded)
  - Isolated run_id defaulting to spotcheck-<model_slug> to preserve existing DB rows
  - Exact 60-episode enumeration (12 patterns x aggressive intensity x 5 repeats)
  - Pre-flight validation, key rotation, signal handling, and summary exports
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure workspace root is in sys.path for harness imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import datetime
import os
import re
import signal
import time
from typing import Any

from harness.adapters.common import MAX_STEPS
from harness.config import EpisodeConfig, enumerate_configs
from harness.providers import get_key_pool
from harness.runner import run_episode
from scripts.run_matrix import (
    PATTERN_TASKS,
    append_crash_report,
    completed_config_hashes,
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

DEFAULT_AGENT_MODEL = "groq/llama-3.1-8b-instant"
DEFAULT_JUDGE_MODEL = "groq/openai/gpt-oss-120b"
REPORT_EVERY_EPISODES = 10


def slugify(text: str) -> str:
    """Convert model name or string to safe filename/run_id slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", text)
    return re.sub(r"-+", "-", slug).strip("-")


def enumerate_spotcheck_configs(model_name: str) -> list[EpisodeConfig]:
    """Enumerate all 60 cross-model spot-check configurations for the given model."""
    configs: list[EpisodeConfig] = []
    all_patterns = list(PATTERN_TASKS.keys())

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
                llms=[model_name],
                repeat_count=5,
                seed_start=0,
            )
        )

    return configs


def main() -> None:
    # Resolve target agent model from environment variable (do NOT hardcode)
    agent_model = os.getenv("CHHAL_MODEL", DEFAULT_AGENT_MODEL)
    model_slug = slugify(agent_model)
    default_run_id = f"spotcheck-{model_slug}"

    parser = argparse.ArgumentParser(
        description="Armavour Cross-Model Spot-Check Benchmark Runner (60 episodes)"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=default_run_id,
        help=f"Unique identifier for matrix run (default: {default_run_id}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate setup and enumerate configs without executing episodes.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=MAX_STEPS,
        help=f"Maximum step budget per episode (default: {MAX_STEPS}, same as the matrix).",
    )
    args = parser.parse_args()

    if args.max_steps:
        os.environ["CHHAL_MAX_STEPS"] = str(args.max_steps)

    run_id = args.run_id
    log_dir = Path("logs")
    results_dir = Path("results")
    ckpt_dir = Path(".checkpoints")

    ckpt_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(run_id, log_dir)
    runtime = get_runtime_versions()
    pool = get_key_pool("groq")

    # Perform Startup Dependency Validation
    validate_dependencies(logger)

    configs = enumerate_spotcheck_configs(agent_model)
    total_configs = len(configs)

    # Verify Configuration Hash Uniqueness
    verify_config_uniqueness(logger, configs)

    # Save Config List Manifest
    config_manifest_path = save_config_manifest(run_id, results_dir, configs)

    # Checkpoint & Resume Query for the isolated run_id
    completed_hashes = completed_config_hashes(run_id)
    remaining_configs = [c for c in configs if c.config_hash not in completed_hashes]
    skipped_configs = [c for c in configs if c.config_hash in completed_hashes]
    skipped_count = len(skipped_configs)

    active_key_idx = pool.current_index() + 1
    total_keys = pool.total_keys()

    # Print Startup Banner
    logger.info("=" * 80)
    logger.info("ARMAVOUR CROSS-MODEL SPOT-CHECK BENCHMARK RUN")
    logger.info("=" * 80)
    logger.info(f"Run ID:               {run_id}")
    logger.info(f"Spot-Check Model:     {agent_model} (CHHAL_MODEL)")
    logger.info(f"Timestamp:            {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    logger.info(f"Git Commit:           {runtime['git_commit']}")
    logger.info(f"Python Version:       {runtime['python_version']}")
    logger.info(f"LiteLLM Version:      {runtime['litellm_version']}")
    logger.info(f"Playwright Version:   {runtime['playwright_version']}")
    logger.info("")
    logger.info(f"Agent Model:          {agent_model}")
    logger.info(f"Judge Model:          {os.getenv('CHHAL_JUDGE_MODEL', DEFAULT_JUDGE_MODEL)}")
    logger.info("")
    logger.info(f"Provider:             Groq (key {active_key_idx}/{total_keys} active)")
    logger.info("Database:             Postgres (Isolated Run ID preserved)")
    logger.info("")
    logger.info(f"Total Spot-Check:     {total_configs} episodes")
    logger.info(f"Already Completed:    {skipped_count}")
    logger.info(f"Remaining to Run:     {len(remaining_configs)}")
    logger.info("=" * 80)

    if skipped_count > 0:
        logger.info(f"Skipping {skipped_count} previously completed episodes for run_id '{run_id}'.")
        for sc in skipped_configs:
            logger.info(
                f"  [SKIP] config_hash={sc.config_hash} pattern={sc.pattern} "
                f"intensity={sc.intensity} model={sc.llm} "
                f"reason=\"Already completed in Postgres under run_id {run_id}\""
            )

    # Save Experiment Manifest & Environment Fingerprint
    manifest_path = save_manifest(run_id, results_dir, runtime, total_configs, total_keys)
    env_fingerprint_path = save_environment_fingerprint(run_id, results_dir, runtime)
    logger.info(f"Immutable experiment manifest saved to {manifest_path}")
    logger.info(f"Immutable config definition saved to {config_manifest_path}")
    logger.info(f"Environment fingerprint saved to {env_fingerprint_path}")

    if args.dry_run:
        logger.info("Dry-run requested. Exiting cleanly without executing episodes.")
        logger.info("=" * 80)
        logger.info("SPOT-CHECK DRY RUN SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Run ID:      {run_id}")
        logger.info(f"Model:       {agent_model}")
        logger.info(f"Episodes:    {total_configs}")
        logger.info(f"Patterns:    {len(PATTERN_TASKS)} (aggressive intensity)")
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
        logger.info("Resume Command:")
        logger.info(f"python scripts/run_spotcheck.py --run-id {run_id}")
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

            logger.info(
                f"[{ep_index:02d}/{total_configs:02d}] "
                f"Pattern={config.pattern} "
                f"Intensity={config.intensity} "
                f"Model={config.llm} "
                f"Agent={config.agent} "
                f"Outcome={outcome or 'CRASH'} "
                f"Steps={steps} "
                f"Duration={dur:.2f}s "
                f"Provider={prov_lat:.2f}s "
                f"Tokens={t_in}/{t_out} "
                f"Cost=${cost:.5f}"
            )

            if idx % REPORT_EVERY_EPISODES == 0 or idx == len(remaining_configs):
                elapsed_s = time.time() - start_time
                completed_so_far = len(executed_rows)
                remaining_so_far = len(remaining_configs) - completed_so_far
                pct = ((skipped_count + completed_so_far) / total_configs) * 100
                avg_dur_so_far = sum(float(r.get("duration_seconds") or 0.0) for r in executed_rows) / completed_so_far
                throughput_ph = (completed_so_far / elapsed_s) * 3600 if elapsed_s > 0 else 0.0
                eta_str, comp_str = format_eta(remaining_so_far, avg_dur_so_far)

                logger.info("=" * 80)
                logger.info(f"SPOT-CHECK PROGRESS ({completed_so_far}/{len(remaining_configs)})")
                logger.info("=" * 80)
                logger.info(f"Completed:                {skipped_count + completed_so_far}/{total_configs} ({pct:.1f}%)")
                logger.info(f"EC={ec_count} DC={dc_count} EF={ef_count} DF={df_count} Crash={crash_count}")
                logger.info(f"Throughput:               {throughput_ph:.1f} ep/hr | ETA: {eta_str}")
                logger.info("=" * 80)

    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

    # Final Export & Manifests
    csv_path, json_path = export_summary_files(
        run_id, results_dir, executed_rows, skipped_count, total_configs, start_time
    )
    elapsed_total_s = time.time() - start_time
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
    logger.info("[OK] SPOT-CHECK BENCHMARK COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Run ID:     {run_id}")
    logger.info(f"Model:      {agent_model}")
    logger.info(f"Episodes:   {total_configs}")
    logger.info(f"Runtime:    {format_seconds(elapsed_total_s)}")
    logger.info(f"Summary:    {csv_path}")
    logger.info(f"Manifest:   {final_manifest_path}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
