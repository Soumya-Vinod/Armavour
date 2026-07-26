import sys

sys.path.insert(0, ".")

from harness.config import enumerate_configs
from harness.logger import engine_from_env, episodes_table
from harness.runner import run_batch
from sqlalchemy import select


RUN_ID = "pilot-01"

PATTERN_TASKS = {
    "basket_sneaking": "bs_ticket",
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


def pilot_configs():
    configs = []
    for pattern in [
        "basket_sneaking",
        "forced_action",
        "subscription_trap",
        "interface_interference",
        "bait_and_switch",
        "drip_pricing",
        "disguised_advertisement",
        "nagging",
        "trick_question",
        "saas_billing",
    ]:  # deterministic only; no soft patterns until judge.py is hardened
        configs.extend(
            enumerate_configs(
                site="ticketing",
                task_id=PATTERN_TASKS[pattern],
                patterns=[pattern],
                intensities=["subtle", "moderate", "aggressive"],
                languages=["en"],
                agents=["computeruse"],
                llms=["groq/llama-3.3-70b-versatile"],
                repeat_count=5,  # 10 patterns x 3 intensities x 5 repeats = 150 episodes
            )
        )
    return configs


def completed_config_hashes(run_id):
    engine = engine_from_env()
    table = episodes_table(engine)
    stmt = select(table.c.config_hash).where(
        table.c.run_id == run_id,
        table.c.outcome.is_not(None),
    )
    with engine.connect() as conn:
        return {row.config_hash for row in conn.execute(stmt)}


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
    print(
        {
            "event": "pilot_episode_end",
            "index": index,
            "pattern": config.pattern,
            "outcome": row["outcome"],
            "steps": row["steps"],
            "cost_usd": row["cost_usd"],
        },
        flush=True,
    )


def main():
    configs = pilot_configs()
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
