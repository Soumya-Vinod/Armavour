import sys

sys.path.insert(0, ".")

from harness.config import enumerate_configs
from harness.runner import run_batch


def rerun_configs():
    return enumerate_configs(
        site="ticketing",
        task_id="dp_ticket",
        patterns=["drip_pricing"],
        intensities=["aggressive"],
        languages=["en"],
        agents=["computeruse"],
        llms=["groq/llama-3.3-70b-versatile"],
        repeat_count=5,
        target_episode_count=5,
    )


def main():
    configs = rerun_configs()
    print(f"Generated {len(configs)} configs")
    run_batch(configs, run_id="pilot-01")


if __name__ == "__main__":
    main()
