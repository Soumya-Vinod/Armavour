#!/usr/bin/env python3
"""
scripts/run_lang_control.py - language x control replication (docs/audit/LANGCTL_PLAN.md).

Does the matrix's control-condition language disparity (CORRECTED_TABLES T2;
REVIEW_ANALYSES §B/§E/§G) replicate on a second model?

  testbed      frozen baseline only, http://localhost:5174 (armavour_data/testbed_baseline), variant "baseline"
  intensity    control only
  patterns     trick_question, confirm_shaming, interface_interference, forced_action, saas_billing
  conditions   (instruction/interface) en/en, en/hi, en/hinglish, hi/hi, hinglish/hinglish,
               enumerated with the same enumerate_configs calls as the matrix's E2 / E2a / E2b
               (scripts/run_matrix.py), seeds 0-9 per cell
  episodes     5 patterns x 5 conditions x 10 seeds = 250, run_id langctl-qwen-t07-01
  agent        computeruse, groq/qwen/qwen3.8-27b, T = 0.7, thinking suppressed, config leak OFF,
               20 steps; judge groq/openai/gpt-oss-120b (confirm_shaming)
               (scripts/run_rerun.configure_environment, unchanged)

Refuses to start unless DATABASE_URL names armavour_langctl and the engine is
connected to it with migration 0007 applied; git works and the tree has no
uncommitted changes to tracked files (code_sha re-checked around every
episode); :5174 answers and serves the baseline (no Free plan element on the
saas_billing page) with a Hindi interface available; the prompt guard passes.

--smoke writes to smoke-langctl-01 and may use --allow-dirty.

Crashes: an episode that crashes is retried, up to 3 attempts in total per
config, counted across invocations in results/langctl/attempts_<run_id>.json.
A config still crashed after 3 attempts is left as a crash row (v2 NC).

Console: no interim looks (LANGCTL_PLAN §2). By default only progress, crash
and rate-limit lines are shown, never per-episode outcomes; the harness's own
stdout (adapter steps etc.) goes to logs/langctl_<run_id>.stdout.log, with
rate-limit and key-rotation lines echoed. --show-outcomes overrides. No
outcome summary file is written (run_matrix.export_summary_files is not used).

Resumable: configs stored with a non-NULL outcome, or with 3 attempts, are skipped.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import contextlib
import datetime
import io
import json
import os
import re
import signal
import time
import urllib.request
from collections.abc import Iterator
from typing import Any, TextIO

from harness.config import EpisodeConfig, enumerate_configs
from harness.providers import get_key_pool
from harness.runner import code_sha, run_episode
from scripts.run_leak_ablation import assert_prompt_has_no_config
from scripts.run_matrix import (
    PATTERN_TASKS,
    append_crash_report,
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
from scripts.run_rerun import (
    AGENT_MODEL,
    JUDGE_MODEL,
    MAX_STEPS,
    NEW_COLUMNS,
    TEMPERATURE,
    _probe_url,
    completed_hashes,
    configure_environment,
    database_name,
    require_clean_tree,
    require_code_sha,
    require_git,
)

DATABASE_NAME = "armavour_langctl"
RUN_ID = "langctl-qwen-t07-01"
SMOKE_RUN_ID = "smoke-langctl-01"
VARIANT = "baseline"
BASE_URL = "http://localhost:5174"
PATTERNS = ("trick_question", "confirm_shaming", "interface_interference", "forced_action", "saas_billing")
# (instruction_language, ui_language)
CONDITIONS = (("en", "en"), ("en", "hi"), ("en", "hinglish"), ("hi", "hi"), ("hinglish", "hinglish"))
SEEDS = 10
MAX_ATTEMPTS = 3
REPORT_EVERY = 10
RESULTS_DIR = Path("results") / "langctl"
# harness stdout lines echoed to the console in quiet mode
PASSTHROUGH = re.compile(r"rate_limit|rate limit|Switching to key|exhausted|tpd|Checkpoint updated|batch_halted|episode_log_failed", re.I)


# ---- design -------------------------------------------------------------------


def condition_of(config: EpisodeConfig) -> tuple[str, str]:
    return (config.instruction_language, config.ui_language)


def enumerate_langctl_configs() -> list[EpisodeConfig]:
    """Same enumerate_configs call shapes as run_matrix E2 / E2a / E2b, control only, seeds 0-9."""
    common = dict(site="ticketing", intensities=["control"], agents=["computeruse"], llms=[AGENT_MODEL],
                  repeat_count=SEEDS, seed_start=0)
    configs: list[EpisodeConfig] = []
    for p in PATTERNS:
        task = PATTERN_TASKS[p]
        configs += enumerate_configs(task_id=task, patterns=[p], ui_languages=["en", "hi", "hinglish"],
                                     instruction_languages=["en", "en", "en"], **common)  # E2 shape
        configs += enumerate_configs(task_id=task, patterns=[p], ui_languages=["hi"], instruction_languages=["hi"], **common)  # E2a
        configs += enumerate_configs(task_id=task, patterns=[p], ui_languages=["hinglish"], instruction_languages=["hinglish"], **common)  # E2b
    return configs


def episode_order(configs: list[EpisodeConfig]) -> list[EpisodeConfig]:
    """Seed-major; within each (seed, pattern) the condition order rotates, so drift hits every condition alike."""
    p_idx = {p: i for i, p in enumerate(PATTERNS)}
    c_idx = {c: i for i, c in enumerate(CONDITIONS)}

    def key(c: EpisodeConfig) -> tuple[int, int, int]:
        return (c.seed, p_idx[c.pattern], (c_idx[condition_of(c)] - c.seed - p_idx[c.pattern]) % len(CONDITIONS))

    return sorted(configs, key=key)


def select_configs(configs: list[EpisodeConfig], only: list[str]) -> list[EpisodeConfig]:
    """--only pattern[:instruction/ui[:seed]] filters (smoke tests)."""
    if not only:
        return configs
    keep = []
    for config in configs:
        for spec in only:
            parts = spec.split(":")
            if parts[0] != config.pattern:
                continue
            if len(parts) > 1 and parts[1] and parts[1] != "/".join(condition_of(config)):
                continue
            if len(parts) > 2 and parts[2] and int(parts[2]) != config.seed:
                continue
            keep.append(config)
            break
    return keep


# ---- attempts ledger ----------------------------------------------------------


class Attempts:
    """Attempts per config_hash, persisted so the 3-attempt cap holds across resumes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.counts: dict[str, int] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def get(self, config_hash: str) -> int:
        return int(self.counts.get(config_hash, 0))

    def add(self, config_hash: str) -> int:
        self.counts[config_hash] = self.get(config_hash) + 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.counts, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
        return self.counts[config_hash]


def pending(order: list[EpisodeConfig], done: set[str], attempts: Attempts) -> list[EpisodeConfig]:
    return [c for c in order if c.config_hash not in done and attempts.get(c.config_hash) < MAX_ATTEMPTS]


# ---- guards -------------------------------------------------------------------


def require_langctl_database(url: str | None = None) -> None:
    name = database_name(url if url is not None else os.getenv("DATABASE_URL", ""))
    if name != DATABASE_NAME:
        raise SystemExit(f"Refusing to start: DATABASE_URL names database {name!r}; this run writes only to {DATABASE_NAME!r}.")


def require_connected_database(engine: Any = None) -> None:
    from sqlalchemy import text

    from harness.logger import engine_from_env

    engine = engine or engine_from_env()
    with engine.connect() as conn:
        name = conn.execute(text("SELECT current_database()")).scalar()
    if name != DATABASE_NAME:
        raise SystemExit(f"Refusing to start: connected to database {name!r}, not {DATABASE_NAME!r}.")


def require_schema(engine: Any = None) -> None:
    from harness.logger import engine_from_env, episodes_table

    engine = engine or engine_from_env()
    columns = {c.name for c in episodes_table(engine).columns}
    missing = [c for c in NEW_COLUMNS if c not in columns]
    if missing:
        raise SystemExit(f"Refusing to start: episodes lacks {missing}; apply migrations through 0007 to {DATABASE_NAME}.")


def refuse_mixed_models(run_id: str, engine: Any = None) -> None:
    from sqlalchemy import select

    from harness.logger import engine_from_env, episodes_table

    engine = engine or engine_from_env()
    table = episodes_table(engine)
    stmt = select(table.c.llm, table.c.testbed_variant).where(table.c.run_id == run_id).distinct()
    with engine.connect() as conn:
        found = [(m, v) for m, v in conn.execute(stmt).all() if m != AGENT_MODEL or v != VARIANT]
    if found:
        raise SystemExit(f"Refusing to start: {run_id} already holds rows from another model or variant: {found}")


def require_baseline_server() -> None:
    """:5174 answers, serves the baseline (no Free plan on saas_billing) and renders a Hindi interface."""
    try:
        with urllib.request.urlopen(BASE_URL, timeout=5) as resp:  # noqa: S310 - fixed localhost URL
            if resp.status != 200:
                raise OSError(f"HTTP {resp.status}")
    except OSError as exc:
        raise SystemExit(f"Refusing to start: baseline testbed at {BASE_URL} is down ({exc}).") from exc
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(_probe_url(BASE_URL), wait_until="networkidle")
            has_free_plan = page.locator("#sb-free").count() > 0
            page.goto(_probe_url(BASE_URL).replace("lang=en", "lang=hi"), wait_until="networkidle")
            hindi = bool(re.search(r"[ऀ-ॿ]", page.inner_text("body")))
            page.close()
        finally:
            browser.close()
    if has_free_plan:
        raise SystemExit(f"Refusing to start: {BASE_URL} renders the Free plan, i.e. the fixed testbed, not the baseline.")
    if not hindi:
        raise SystemExit(f"Refusing to start: {BASE_URL} with lang=hi renders no Devanagari text.")


# ---- quiet console ------------------------------------------------------------


class _Tee(io.TextIOBase):
    """Write everything to `sink`; echo lines matching PASSTHROUGH to `console`."""

    def __init__(self, sink: TextIO, console: TextIO) -> None:
        self.sink, self.console, self._buf = sink, console, ""

    def write(self, s: str) -> int:
        self.sink.write(s)
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if PASSTHROUGH.search(line):
                self.console.write(line + "\n")
                self.console.flush()
        return len(s)

    def flush(self) -> None:
        self.sink.flush()
        self.console.flush()


@contextlib.contextmanager
def quiet_stdout(log_path: Path, enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as sink:
        original = sys.stdout
        sys.stdout = _Tee(sink, original)
        try:
            yield
        finally:
            sys.stdout = original


def episode_line(n: int, total: int, config: EpisodeConfig, row: dict[str, Any], attempt: int, show_outcomes: bool) -> str:
    cond = "/".join(condition_of(config))
    base = f"[{n:03d}/{total:03d}] {config.pattern} {cond} seed={config.seed}"
    if row.get("outcome") is None:
        return f"{base} CRASH attempt {attempt}/{MAX_ATTEMPTS}: {row.get('error_type')}"
    if show_outcomes:
        return (f"{base} v1={row.get('outcome')} end={row.get('terminal_reason')} steps={row.get('steps', 0)} "
                f"{float(row.get('duration_seconds') or 0.0):.1f}s")
    return f"{base} done"


# ---- main ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Language x control replication, baseline testbed (250 episodes)")
    parser.add_argument("--dry-run", action="store_true", help="Run every guard and enumerate episodes, then exit.")
    parser.add_argument("--only", action="append", default=[], metavar="PATTERN[:INSTR/UI[:SEED]]",
                        help="Restrict to matching configs (smoke tests), e.g. trick_question:hi/hi:0. Repeatable.")
    parser.add_argument("--max-episodes", type=int, default=None, help="Stop after this many episodes (smoke tests).")
    parser.add_argument("--smoke", action="store_true", help=f"Write to {SMOKE_RUN_ID} instead of {RUN_ID}.")
    parser.add_argument("--allow-dirty", action="store_true", help="Smoke test only: skip the dirty-tree check.")
    parser.add_argument("--show-outcomes", action="store_true", help="Print per-episode outcomes (overrides the no-interim-looks default).")
    args = parser.parse_args(argv)
    if args.allow_dirty and not args.smoke:
        parser.error("--allow-dirty is only for the smoke test (--smoke); the full run must run from a clean commit")
    run_id = SMOKE_RUN_ID if args.smoke else RUN_ID

    configure_environment()
    os.environ["BASE_URL"] = BASE_URL
    os.environ["ARMAVOUR_TESTBED_VARIANT"] = VARIANT
    require_langctl_database()
    head = require_git()
    dirty = require_clean_tree(allow_dirty=args.allow_dirty)
    start_sha = code_sha()
    if not dirty and start_sha != head:
        raise SystemExit(f"Refusing to start: code_sha() returned {start_sha!r}, expected the clean commit {head!r}.")
    assert_prompt_has_no_config(AGENT_MODEL)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    Path(".checkpoints").mkdir(parents=True, exist_ok=True)
    logger = setup_logger(f"langctl_{run_id}", Path("logs"))
    runtime = get_runtime_versions()
    pool = get_key_pool("groq")

    validate_dependencies(logger)
    require_connected_database()
    require_schema()
    refuse_mixed_models(run_id)
    require_baseline_server()

    all_configs = enumerate_langctl_configs()
    verify_config_uniqueness(logger, all_configs)
    if len(all_configs) != len(PATTERNS) * len(CONDITIONS) * SEEDS:
        raise SystemExit(f"Enumerated {len(all_configs)} configs, expected {len(PATTERNS) * len(CONDITIONS) * SEEDS}")
    configs = select_configs(all_configs, args.only)
    if not configs:
        raise SystemExit(f"--only {args.only} matches no config")

    attempts = Attempts(RESULTS_DIR / f"attempts_{run_id}.json")
    done = completed_hashes(run_id)
    order = episode_order(configs)
    plan = pending(order, done, attempts)
    if args.max_episodes is not None:
        plan = plan[: args.max_episodes]
    total = len(configs)
    skipped = total - len(pending(order, done, attempts))
    exhausted = sum(1 for c in order if c.config_hash not in done and attempts.get(c.config_hash) >= MAX_ATTEMPTS)

    save_config_manifest(run_id, RESULTS_DIR, configs)
    save_manifest(run_id, RESULTS_DIR, runtime, len(configs), pool.total_keys())
    save_environment_fingerprint(run_id, RESULTS_DIR, runtime)

    logger.info("=" * 80)
    logger.info("ARMAVOUR LANGUAGE x CONTROL REPLICATION (baseline testbed)")
    logger.info("=" * 80)
    logger.info(f"Timestamp:      {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    logger.info(f"Code SHA:       {start_sha}")
    if dirty:
        logger.info(f"WARNING:        --allow-dirty (smoke only): {len(dirty)} tracked file(s) uncommitted, rows carry a -dirty code_sha")
    logger.info(f"Agent / judge:  {AGENT_MODEL} / {JUDGE_MODEL}")
    logger.info(f"Temperature:    {TEMPERATURE}   Max steps: {MAX_STEPS}   Config leak: OFF (guard passed)")
    logger.info(f"Testbed:        {VARIANT} {BASE_URL}   run_id {run_id}")
    logger.info(f"Episodes:       {total} planned, {skipped} already stored or out of attempts ({exhausted} out of attempts), {len(plan)} to run now")
    logger.info(f"Console:        {'per-episode outcomes SHOWN (--show-outcomes)' if args.show_outcomes else 'no per-episode outcomes (no interim looks)'}")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("Dry run: all guards passed. Exiting without running episodes.")
        return

    executed: list[dict[str, Any]] = []
    start = time.time()
    stdout_log = Path("logs") / f"langctl_{run_id}.stdout.log"

    def finish(status: str) -> None:
        save_final_manifest(run_id, RESULTS_DIR, status, executed, len(done), len(configs), time.time() - start,
                            pool.get_rotation_summary())

    def on_signal(signum: int, frame: Any) -> None:
        logger.info(f"INTERRUPTED after {len(executed)} episodes; rerun the same command to resume.")
        finish("interrupted")
        sys.exit(130)

    signal.signal(signal.SIGINT, on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_signal)

    try:
        for idx, config in enumerate(plan, start=1):
            while True:
                require_code_sha(start_sha)
                with quiet_stdout(stdout_log, enabled=not args.show_outcomes):
                    row = run_episode(config, run_id=run_id, log=True)
                attempt = attempts.add(config.config_hash)
                if row.get("code_sha") != start_sha:
                    raise SystemExit(
                        f"Stopping: row {run_id}/{config.config_hash} was stored with code_sha {row.get('code_sha')!r}, "
                        f"expected {start_sha!r}. Delete that row, restore the tree, then rerun to resume."
                    )
                executed.append(row)
                pool.record_episode()
                if row.get("outcome") is None:
                    append_crash_report(RESULTS_DIR, run_id, config, row)
                logger.info(episode_line(skipped + idx, total, config, row, attempt, args.show_outcomes))
                if row.get("outcome") is not None or attempt >= MAX_ATTEMPTS:
                    break
            if idx % REPORT_EVERY == 0 or idx == len(plan):
                avg = sum(float(r.get("duration_seconds") or 0.0) for r in executed) / len(executed)
                eta, _ = format_eta(len(plan) - idx, avg)
                logger.info(f"PROGRESS {skipped + idx}/{total} | elapsed {format_seconds(time.time() - start)} | ETA {eta}")
    except KeyboardInterrupt:
        # Includes TPDExhaustedError (all keys out of daily tokens): no row, no attempt counted; rerun to resume.
        on_signal(signal.SIGINT, None)

    finish("completed" if args.max_episodes is None and not args.only else "partial")
    logger.info("[OK] batch finished. Analyse only after the full run: python scripts/analyze_lang_control.py")


if __name__ == "__main__":
    main()
