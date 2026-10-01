#!/usr/bin/env python3
"""
Re-run of interface_interference and confirm_shaming at aggressive intensity
across all five arms, post identifier-fix.

Purpose: validity finding — does the null persist with corrected testbed
identifiers and base weights (groq/llama-3.3-70b-versatile)?

Pre-fix episodes retained in DB under original run_ids.
This run uses run_id="rerun-post-id-fix-01".



Arms:
  E1a: computeruse, en, seeds 0-9
  E1b: browseruse, en, seeds 0-9
  E2:  computeruse, en instruction → hi+hinglish UI, seeds 0-9
  E2a: computeruse, hi instruction → hi UI, seeds 0-9
  E2b: computeruse, hinglish instruction → hinglish UI, seeds 0-9

Total: 140 episodes
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from sqlalchemy import select

from harness.config import EpisodeConfig, enumerate_configs
from harness.logger import engine_from_env, episodes_table
from harness.runner import run_batch

load_dotenv()

RUN_ID = "rerun-post-id-fix-01"
DEFAULT_MODEL = os.getenv("CHHAL_MODEL", "groq/llama-3.3-70b-versatile")
DEFAULT_MAX_STEPS = int(os.getenv("CHHAL_MAX_STEPS", "5"))

PATTERN_TASKS = {
    "interface_interference": "ii_renew",
    "confirm_shaming": "cs_donation",
}


def build_configs(model: str = DEFAULT_MODEL) -> list[EpisodeConfig]:
    """
    Enumerate all 140 configurations for the post-identifier-fix rerun:
      - E1a:  20 episodes (2 patterns × aggressive × en/en × computeruse × 10 seeds)
      - E1b:  20 episodes (2 patterns × aggressive × en/en × browseruse × 10 seeds)
      - E2:   60 episodes (2 patterns × aggressive × [en, hi, hinglish] UI / en instr × computeruse × 10 seeds)
      - E2a:  20 episodes (2 patterns × aggressive × hi UI / hi instr × computeruse × 10 seeds)
      - E2b:  20 episodes (2 patterns × aggressive × hinglish UI / hinglish instr × computeruse × 10 seeds)
    """
    configs: list[EpisodeConfig] = []

    # 1. E1a: computeruse, en instruction, en UI, seeds 0-9 (20 episodes)
    for p, task_id in PATTERN_TASKS.items():
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=task_id,
                patterns=[p],
                intensities=["aggressive"],
                ui_languages=["en"],
                instruction_languages=["en"],
                agents=["computeruse"],
                llms=[model],
                repeat_count=10,
                seed_start=0,
            )
        )

    # 2. E1b: browseruse, en instruction, en UI, seeds 0-9 (20 episodes)
    for p, task_id in PATTERN_TASKS.items():
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=task_id,
                patterns=[p],
                intensities=["aggressive"],
                ui_languages=["en"],
                instruction_languages=["en"],
                agents=["browseruse"],
                llms=[model],
                repeat_count=10,
                seed_start=0,
            )
        )

    # 3. E2: computeruse, en instruction -> en, hi, hinglish UI, seeds 0-9 (60 episodes)
    for p, task_id in PATTERN_TASKS.items():
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=task_id,
                patterns=[p],
                intensities=["aggressive"],
                ui_languages=["en", "hi", "hinglish"],
                instruction_languages=["en", "en", "en"],
                agents=["computeruse"],
                llms=[model],
                repeat_count=10,
                seed_start=0,
            )
        )

    # 4. E2a: computeruse, hi instruction -> hi UI, seeds 0-9 (20 episodes)
    for p, task_id in PATTERN_TASKS.items():
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=task_id,
                patterns=[p],
                intensities=["aggressive"],
                ui_languages=["hi"],
                instruction_languages=["hi"],
                agents=["computeruse"],
                llms=[model],
                repeat_count=10,
                seed_start=0,
            )
        )

    # 5. E2b: computeruse, hinglish instruction -> hinglish UI, seeds 0-9 (20 episodes)
    for p, task_id in PATTERN_TASKS.items():
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=task_id,
                patterns=[p],
                intensities=["aggressive"],
                ui_languages=["hinglish"],
                instruction_languages=["hinglish"],
                agents=["computeruse"],
                llms=[model],
                repeat_count=10,
                seed_start=0,
            )
        )

    return configs


def completed_config_hashes(run_id: str) -> set[str]:
    """Retrieve set of already completed config_hashes for idempotency and resuming."""
    try:
        engine = engine_from_env()
        table = episodes_table(engine)
        stmt = select(table.c.config_hash).where(
            table.c.run_id == run_id,
            table.c.outcome.is_not(None),
        )
        with engine.connect() as conn:
            return set(conn.execute(stmt).scalars().all())
    except Exception as exc:
        logging.warning("Could not fetch completed config hashes from DB: %s", exc)
        return set()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-run interface_interference and confirm_shaming post identifier-fix across all 5 arms."
    )
    parser.add_argument("--run-id", default=RUN_ID, help=f"Run identifier (default: {RUN_ID})")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"LLM model identifier (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS, help=f"Maximum steps per episode (default: {DEFAULT_MAX_STEPS})")
    parser.add_argument("--dry-run", action="store_true", help="Print config breakdown and exit without running")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of remaining episodes to execute")
    args = parser.parse_args()

    os.environ["CHHAL_MAX_STEPS"] = str(args.max_steps)

    configs = build_configs(model=args.model)
    print(f"Generated {len(configs)} total episode configurations across all 5 arms.")
    print(f"Run ID: {args.run_id}")
    print(f"Model: {args.model}")
    print(f"Max Steps per episode: {args.max_steps}")

    if args.dry_run:
        arm_counts: dict[str, int] = {}
        for c in configs:
            if c.agent == "browseruse":
                arm = "E1b"
            elif c.instruction_language == "hi":
                arm = "E2a"
            elif c.instruction_language == "hinglish":
                arm = "E2b"
            elif c.ui_language in ("hi", "hinglish"):
                arm = "E2"
            else:
                arm = "E1a"
            arm_counts[arm] = arm_counts.get(arm, 0) + 1
        print("\nConfig breakdown by arm:")
        for arm, count in sorted(arm_counts.items()):
            print(f"  {arm}: {count} episodes")
        print(f"  Total: {sum(arm_counts.values())} episodes")
        return

    done = completed_config_hashes(args.run_id)
    todo = [c for c in configs if c.config_hash not in done]

    print(f"Completed in DB: {len(done)}")
    print(f"Remaining to run: {len(todo)}")

    if not todo:
        print("All configurations are already completed in the database. Nothing to do.")
        return

    if args.limit is not None and args.limit > 0:
        todo = todo[:args.limit]
        print(f"Executing batch capped at limit: {len(todo)} episodes")

    print(f"\nStarting batch execution of {len(todo)} episodes...")
    run_batch(
        todo,
        run_id=args.run_id,
        on_episode_end=lambda i, c, r: print(
            f"[{i+1}/{len(todo)}] pattern={c.pattern} agent={c.agent} ui_lang={c.ui_language} instr_lang={c.instruction_language} seed={c.seed} -> outcome={r.get('outcome')} (avoided={r.get('avoided')}, placed={r.get('placed')})"
        ),
    )


if __name__ == "__main__":
    main()
