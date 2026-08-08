# scripts/rerun_disguised_ad.py
import sys, uuid
sys.path.insert(0, ".")
from harness.config import enumerate_configs
from harness.runner import run_batch

RUN_ID = "rerun-disguised-ad-v2"

def configs():
    c = enumerate_configs(
        site="ticketing", task_id="da_cheapest",
        patterns=["disguised_advertisement"],
        intensities=["control", "subtle", "moderate", "aggressive"],
        languages=["en"], agents=["computeruse"],
        llms=["groq/llama-3.3-70b-versatile"],
        repeat_count=10, seed_start=0,
    )
    c += enumerate_configs(
        site="ticketing", task_id="da_cheapest",
        patterns=["disguised_advertisement"],
        intensities=["aggressive"],
        languages=["en"], agents=["computeruse"],
        llms=["groq/llama-3.1-8b-instant"],
        repeat_count=5, seed_start=0,
    )
    return c

if __name__ == "__main__":
    cfgs = configs()
    print(f"{len(cfgs)} configs")
    run_batch(cfgs, run_id=RUN_ID,
              on_episode_end=lambda i, c, r: print(i, c.intensity, r["outcome"]))
    