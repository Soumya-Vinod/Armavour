import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from harness.config import enumerate_configs
from harness.logger import engine_from_env, episodes_table
from harness.runner import run_batch

RUN_ID = "pilot-soft-01"

PATTERN_TASKS = {
    "false_urgency": "fu_best",
    "confirm_shaming": "cs_donation",
}


def soft_configs():
    configs = []
    for pattern, task_id in PATTERN_TASKS.items():
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=task_id,
                patterns=[pattern],
                intensities=["subtle", "moderate", "aggressive"],
                languages=["en"],
                agents=["computeruse"],
                llms=["groq/llama-3.3-70b-versatile"],
                repeat_count=5,
            )
        )
    return configs


def print_episode_start(index, config):
    print(
        {
            "event": "pilot_episode_start",
            "index": index,
            "pattern": config.pattern,
            "intensity": config.intensity,
            "seed": config.seed,
        },
        flush=True,
    )


def print_episode_end(index, config, row):
    payload = {
        "event": "pilot_episode_end",
        "index": index,
        "pattern": config.pattern,
        "outcome": row["outcome"],
        "steps": row["steps"],
        "cost_usd": row["cost_usd"],
    }
    if row["outcome"] is None and row["trace"]:
        last_trace = row["trace"][-1]
        if isinstance(last_trace, dict) and "exception" in last_trace:
            payload["exception"] = last_trace["exception"]
    print(payload, flush=True)


def completed_config_hashes(run_id):
    engine = engine_from_env()
    table = episodes_table(engine)
    stmt = select(table.c.config_hash).where(
        table.c.run_id == run_id,
        table.c.outcome.is_not(None),
    )
    with engine.connect() as conn:
        return {row.config_hash for row in conn.execute(stmt)}


def main():
    configs = soft_configs()
    completed = completed_config_hashes(RUN_ID)
    remaining = [config for config in configs if config.config_hash not in completed]

    print(f"Generated {len(configs)} configs")
    print(f"Skipping {len(completed)} completed configs")
    print(f"Running {len(remaining)} remaining configs")

    run_batch(
        remaining,
        run_id=RUN_ID,
        on_episode_start=print_episode_start,
        on_episode_end=print_episode_end,
    )


if __name__ == "__main__":
    main()
