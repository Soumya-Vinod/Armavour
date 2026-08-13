from __future__ import annotations

import sys
import time
from dotenv import load_dotenv

sys.path.insert(0, ".")

from harness.config import EpisodeConfig, enumerate_configs
from harness.runner import run_batch, PRECHECK_PATTERN_TASKS

load_dotenv()

RUN_ID = f"pilot-e1b-10episodes-{int(time.time())}"
PATTERN_TASKS = dict(PRECHECK_PATTERN_TASKS)

patterns = [
    "basket_sneaking",
    "false_urgency",
    "confirm_shaming",
    "forced_action",
    "subscription_trap",
    "interface_interference",
    "bait_and_switch",
    "drip_pricing",
    "disguised_advertisement",
    "nagging",
]

def build_10_e1b_configs() -> list[EpisodeConfig]:
    configs = []
    for i, p in enumerate(patterns):
        intensity = ["subtle", "moderate", "aggressive", "control"][i % 4]
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=PATTERN_TASKS[p],
                patterns=[p],
                intensities=[intensity],
                languages=["en"],
                agents=["browseruse"],
                llms=["groq/llama-3.3-70b-versatile"],
                repeat_count=1,
                seed_start=10 + i,
            )
        )
    return configs[:10]

def main():
    configs = build_10_e1b_configs()
    print("=" * 80)
    print(f"RUNNING 10 E1b BROWSERUSE EPISODES (RUN ID: {RUN_ID})")
    print(f"Generated {len(configs)} episode configs.")
    print("=" * 80)

    for i, cfg in enumerate(configs, start=1):
        print(f"  [{i}/10] pattern={cfg.pattern}, intensity={cfg.intensity}, task_id={cfg.task_id}")

    print("\nStarting execution...\n")
    rows = run_batch(configs, run_id=RUN_ID, log=True)

    print("\n" + "=" * 80)
    print("PILOT E1b 10-EPISODE RUN COMPLETE SUMMARY")
    print("=" * 80)
    for i, row in enumerate(rows, start=1):
        outcome = row.get("outcome")
        placed = row.get("placed")
        avoided = row.get("avoided")
        pattern = row.get("pattern")
        intensity = row.get("intensity")
        print(f"Episode {i:02d}: pattern={pattern:<24} intensity={intensity:<10} outcome={outcome} (placed={placed}, avoided={avoided})")

if __name__ == "__main__":
    main()
