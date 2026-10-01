#!/usr/bin/env python3
"""
scripts/run_leak_ablation.py — F6 config-leak ablation, two arms x 200 episodes.

Runs a seed-paired slice of matrix-full-e1e2's E1a cells twice on the current
harness, differing ONLY in whether the episode config (pattern, intensity,
seed, config_hash, ...) is in the ComputerUse prompt:

  --arm off  run_id ablation-noconfig-01  config absent (guard aborts if present)
  --arm on   run_id ablation-config-01    CHHAL_ABLATION_LEAK_CONFIG=1 re-injects the
                                          matrix-era "config": to_dict() (guard aborts if absent)

Common to both arms:
  agent     computeruse, --agent-model (default groq/qwen/qwen3.8-27b; the matrix's
            llama-3.3-70b-versatile is retired). Both arms must use the same model;
            the runner refuses to mix models across or within the ablation run_ids.
  cells     10 scored patterns x {control, aggressive} x seeds 0-9 = 200
  language  English UI + English instruction (same as E1a)
  steps     20 (CHHAL_MAX_STEPS; E1a ran under the harness default of 20 --
            scripts/run_matrix.py had no --max-steps option at a2f4ef7)

The configs are the matrix's E1a cells with the agent model swapped in, so the
two arms share config_hashes and pair on them (scripts/analyze_ablation.py).
With a model other than llama-3.3-70b-versatile they no longer match the
matrix's hashes, and the matrix comparison is skipped. Resumable and idempotent like the
matrix: configs already completed under this run_id are skipped, and
harness/logger.py upserts on (config_hash, run_id).

Rows go to whatever DATABASE_URL points at. armavour_audit is the read-only
audit restore and is refused.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure workspace root is in sys.path for harness imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import datetime
import json
import os
import signal
import time
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from harness.adapters.computeruse import CONFIG_LEAK_ENV
from harness.config import EpisodeConfig, enumerate_configs
from harness.providers import get_key_pool
from harness.runner import code_sha, run_episode
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

ARM_RUN_IDS = {"off": "ablation-noconfig-01", "on": "ablation-config-01"}
# groq/llama-3.3-70b-versatile (the matrix agent) has been retired by Groq
# (model_not_found), so both arms default to a current model.
DEFAULT_AGENT_MODEL = "groq/qwen/qwen3.8-27b"
MATRIX_MAX_STEPS = 20
EXCLUDED_PATTERNS = {"disguised_advertisement", "false_urgency"}  # scripts/analysis.py:79
INTENSITIES = ["control", "aggressive"]
READ_ONLY_DATABASES = {"armavour_audit"}
REPORT_EVERY_EPISODES = 25


def enumerate_ablation_configs(agent_model: str = DEFAULT_AGENT_MODEL) -> list[EpisodeConfig]:
    """The E1a configs (scripts/run_matrix.py batch 1) restricted to the ablation cells."""
    configs: list[EpisodeConfig] = []
    for pattern, task_id in PATTERN_TASKS.items():
        if pattern in EXCLUDED_PATTERNS:
            continue
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=task_id,
                patterns=[pattern],
                intensities=INTENSITIES,
                ui_languages=["en"],
                instruction_languages=["en"],
                agents=["computeruse"],
                llms=[agent_model],
                repeat_count=10,
                seed_start=0,
            )
        )
    return configs


def refuse_read_only_database() -> None:
    url = os.getenv("DATABASE_URL", "")
    db_name = urlparse(url.replace("postgresql+psycopg", "postgresql", 1)).path.lstrip("/")
    if db_name in READ_ONLY_DATABASES:
        raise SystemExit(
            f"DATABASE_URL points at '{db_name}', the read-only audit restore. "
            "Point it at a writable database (see SPRINT_REPORT.md Phase 4)."
        )


def _probe_prompt(agent_model: str = DEFAULT_AGENT_MODEL) -> tuple[str, EpisodeConfig]:
    """Build one real ComputerUse prompt with a stubbed provider; return its serialized content."""
    from harness.adapters import computeruse

    captured: list[str] = []

    def fake_completion(**kwargs: Any) -> Any:
        captured.append(kwargs["messages"][0]["content"])
        message = SimpleNamespace(content='{"reasoning": "", "action": "done", "index": 0, "value": null}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    probe = enumerate_ablation_configs(agent_model)[-1]
    original = computeruse.completion_with_rotation
    computeruse.completion_with_rotation = fake_completion
    try:
        adapter = computeruse.Adapter(model=probe.llm)
        adapter.provider_latency_seconds = 0.0
        adapter._next_action("probe task", probe, [], [])
    finally:
        computeruse.completion_with_rotation = original
    return captured[0], probe


def assert_prompt_has_no_config(agent_model: str = DEFAULT_AGENT_MODEL) -> None:
    """Arm off: fail if any config key or value reaches the prompt."""
    content, probe = _probe_prompt(agent_model)
    # Scan the whole serialized prompt, not just top-level keys: the probe has
    # no elements and a neutral task, so none of these can occur legitimately.
    json.loads(content)
    leaked = [k for k in ("config", "pattern", "intensity", "config_hash", "seed", "task_id") if f'"{k}"' in content]
    leaked += [v for v in (probe.pattern, probe.intensity, probe.config_hash, probe.task_id) if v in content]
    if leaked:
        raise SystemExit(f"Harness still leaks the episode config into the agent prompt: {leaked}")


def assert_prompt_has_config(agent_model: str = DEFAULT_AGENT_MODEL) -> None:
    """Arm on: fail unless the prompt carries exactly the matrix-era payload "config": to_dict()."""
    content, probe = _probe_prompt(agent_model)
    prompt = json.loads(content)
    expected = json.loads(json.dumps(probe.to_dict()))
    if prompt.get("config") != expected:
        raise SystemExit(
            f"Config arm requested but the prompt does not carry the episode config "
            f"(got {prompt.get('config')!r}); is {CONFIG_LEAK_ENV}=1 reaching harness/adapters/computeruse.py?"
        )


def refuse_mixed_models(run_id: str, agent_model: str, *, engine: Any = None) -> None:
    """Refuse to start if this run_id or either arm's run_id already holds rows from another llm.

    The two arms are only comparable if they ran the same model; a resumed arm
    must not mix models either.
    """
    from sqlalchemy import select

    from harness.logger import engine_from_env, episodes_table

    engine = engine or engine_from_env()
    table = episodes_table(engine)
    run_ids = sorted({run_id, *ARM_RUN_IDS.values()})
    stmt = select(table.c.run_id, table.c.llm).where(table.c.run_id.in_(run_ids)).distinct()
    with engine.connect() as conn:
        found = [(r, m) for r, m in conn.execute(stmt).all() if m != agent_model]
    if found:
        detail = ", ".join(f"{r}: {m}" for r, m in sorted(found))
        raise SystemExit(
            f"Refusing to start: --agent-model is {agent_model!r} but existing ablation rows use another model "
            f"({detail}). Both arms must run the same model; use a new database or matching --agent-model."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Armavour F6 config-leak ablation runner (200 episodes per arm)")
    parser.add_argument(
        "--arm", required=True, choices=sorted(ARM_RUN_IDS),
        help="off: config absent from the prompt (ablation-noconfig-01); "
             "on: matrix-era config re-injected (ablation-config-01).",
    )
    parser.add_argument("--run-id", type=str, default=None, help="Override the arm's default run_id.")
    parser.add_argument(
        "--agent-model", type=str, default=DEFAULT_AGENT_MODEL,
        help=f"LiteLLM agent model for this arm (default {DEFAULT_AGENT_MODEL}); both arms must match.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate setup and enumerate configs without running.")
    args = parser.parse_args()

    # Same agent model in both arms and the E1a step budget, regardless of the shell's .env.
    os.environ["CHHAL_MODEL"] = args.agent_model
    os.environ["CHHAL_MAX_STEPS"] = str(MATRIX_MAX_STEPS)
    # The arm alone decides the leak switch; a stray shell value cannot flip the off arm.
    if args.arm == "on":
        os.environ[CONFIG_LEAK_ENV] = "1"
    else:
        os.environ.pop(CONFIG_LEAK_ENV, None)

    refuse_read_only_database()
    if args.arm == "on":
        assert_prompt_has_config(args.agent_model)
    else:
        assert_prompt_has_no_config(args.agent_model)

    run_id = args.run_id or ARM_RUN_IDS[args.arm]
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)
    Path(".checkpoints").mkdir(parents=True, exist_ok=True)

    logger = setup_logger(run_id, Path("logs"))
    runtime = get_runtime_versions()
    pool = get_key_pool("groq")

    validate_dependencies(logger)
    refuse_mixed_models(run_id, args.agent_model)

    configs = enumerate_ablation_configs(args.agent_model)
    total_configs = len(configs)
    verify_config_uniqueness(logger, configs)
    config_manifest_path = save_config_manifest(run_id, results_dir, configs)

    completed_hashes = completed_config_hashes(run_id)
    remaining_configs = [c for c in configs if c.config_hash not in completed_hashes]
    skipped_count = total_configs - len(remaining_configs)

    logger.info("=" * 80)
    logger.info("ARMAVOUR F6 CONFIG-LEAK ABLATION")
    logger.info("=" * 80)
    logger.info(f"Run ID:               {run_id}")
    logger.info(f"Timestamp:            {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    logger.info(f"Code SHA:             {code_sha()}")
    logger.info(f"Agent Model:          {args.agent_model}")
    logger.info(f"Judge Model:          {os.getenv('CHHAL_JUDGE_MODEL', 'groq/openai/gpt-oss-120b')}")
    logger.info(f"Max Steps:            {MATRIX_MAX_STEPS}")
    logger.info(f"Provider:             Groq (key {pool.current_index() + 1}/{pool.total_keys()} active)")
    logger.info(f"Arm:                  {args.arm}")
    logger.info("Prompt leak guard:    PASSED ("
                + ("matrix-era config present" if args.arm == "on" else "no config in ComputerUse prompt") + ")")
    logger.info(f"Total Configurations: {total_configs}")
    logger.info(f"Already Completed:    {skipped_count}")
    logger.info(f"Remaining:            {len(remaining_configs)}")
    logger.info("=" * 80)

    manifest_path = save_manifest(run_id, results_dir, runtime, total_configs, pool.total_keys())
    env_fingerprint_path = save_environment_fingerprint(run_id, results_dir, runtime)
    logger.info(f"Manifest: {manifest_path} | Configs: {config_manifest_path} | Environment: {env_fingerprint_path}")

    if args.dry_run:
        logger.info("Dry-run requested. Exiting cleanly without executing episodes.")
        sys.exit(0)

    executed_rows: list[dict[str, Any]] = []
    start_time = time.time()

    def signal_handler(signum: int, frame: Any) -> None:
        elapsed_s = time.time() - start_time
        logger.info("=" * 80)
        logger.info(f"RUN INTERRUPTED -- completed {skipped_count + len(executed_rows)}/{total_configs}")
        logger.info(f"Resume Command: python scripts/run_leak_ablation.py --arm {args.arm} --run-id {run_id}")
        logger.info("=" * 80)
        export_summary_files(run_id, results_dir, executed_rows, skipped_count, total_configs, start_time)
        save_final_manifest(
            run_id, results_dir, "interrupted", executed_rows, skipped_count, total_configs, elapsed_s,
            pool.get_rotation_summary(),
        )
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    counts = {"EC": 0, "DC": 0, "EF": 0, "DF": 0, "CRASH": 0}
    try:
        for idx, config in enumerate(remaining_configs, start=1):
            row = run_episode(config, run_id=run_id, log=True)
            executed_rows.append(row)
            pool.record_episode()

            outcome = row.get("outcome")
            counts[outcome or "CRASH"] = counts.get(outcome or "CRASH", 0) + 1
            if outcome is None:
                append_crash_report(results_dir, run_id, config, row)

            logger.info(
                f"[{skipped_count + idx:03d}/{total_configs:03d}] "
                f"Pattern={config.pattern} Intensity={config.intensity} Seed={config.seed} "
                f"Outcome={outcome or 'CRASH'} Steps={row.get('steps', 0)} "
                f"Duration={float(row.get('duration_seconds') or 0.0):.2f}s "
                f"Tokens={row.get('in_tokens') or 0}/{row.get('out_tokens') or 0}"
            )

            if idx % REPORT_EVERY_EPISODES == 0 or idx == len(remaining_configs):
                elapsed_s = time.time() - start_time
                avg_dur = sum(float(r.get("duration_seconds") or 0.0) for r in executed_rows) / len(executed_rows)
                eta_str, _ = format_eta(len(remaining_configs) - idx, avg_dur)
                logger.info(
                    f"PROGRESS {skipped_count + idx}/{total_configs} | "
                    + " ".join(f"{k}={v}" for k, v in counts.items())
                    + f" | elapsed {format_seconds(elapsed_s)} | ETA {eta_str}"
                )
    except KeyboardInterrupt:
        # Includes harness.providers.TPDExhaustedError (every key out of daily tokens):
        # state is preserved and the same command resumes.
        signal_handler(signal.SIGINT, None)

    elapsed_total_s = time.time() - start_time
    csv_path, _ = export_summary_files(run_id, results_dir, executed_rows, skipped_count, total_configs, start_time)
    save_final_manifest(
        run_id, results_dir, "completed", executed_rows, skipped_count, total_configs, elapsed_total_s,
        pool.get_rotation_summary(),
    )
    logger.info(f"[OK] ABLATION COMPLETE: {run_id}, {total_configs} configs, runtime {format_seconds(elapsed_total_s)}")
    logger.info(f"Summary: {csv_path}")
    logger.info("Next: python scripts/analyze_ablation.py")


if __name__ == "__main__":
    main()
