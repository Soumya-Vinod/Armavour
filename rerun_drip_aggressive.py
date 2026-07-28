"""
Scoped rerun: drip_pricing / aggressive only, 5 episodes.
Run after confirming the testbed fix (fee hidden until Pay click).
"""
import os
import uuid

from harness.config import enumerate_configs
from harness.runner import run_episode, _temporary_env

DEFAULT_DEMO_MAX_STEPS = 6  # match pilot step budget; adjust if pilot used a different value


def rerun_configs():
    return enumerate_configs(
        site="ticketing",
        task_id="dp_ticket",
        patterns=["drip_pricing"],
        intensities=["aggressive"],
        languages=["en"],
        agents=["computeruse"],
        llms=[os.getenv("CHHAL_MODEL", "groq/llama-3.3-70b-versatile")],
        repeat_count=5,
    )


def main():
    configs = rerun_configs()
    run_id = f"rerun-drip-aggressive-{uuid.uuid4().hex}"
    rows = []
    with _temporary_env(
        CHHAL_MAX_STEPS=os.getenv("CHHAL_DEMO_MAX_STEPS", str(DEFAULT_DEMO_MAX_STEPS)),
        CHHAL_PROGRESS="1",
    ):
        for index, config in enumerate(configs, start=1):
            print({
                "event": "episode_start",
                "index": index,
                "total": len(configs),
                "intensity": config.intensity,
                "seed": config.seed,
                "llm": config.llm,
            }, flush=True)
            row = run_episode(config, run_id=run_id, log=True)
            rows.append(row)
            print({
                "event": "episode_end",
                "index": index,
                "outcome": row["outcome"],
                "steps": row["steps"],
                "cost_usd": row["cost_usd"],
            }, flush=True)

    outcomes = {}
    for row in rows:
        outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
    print({"episodes": len(rows), "outcomes": outcomes})
    for row in rows:
        print({key: row[key] for key in ("config_hash", "pattern", "outcome", "cost_usd")})


if __name__ == "__main__":
    main()