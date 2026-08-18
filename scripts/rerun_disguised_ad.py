import sys
sys.path.insert(0, ".")
from sqlalchemy import select
from harness.config import enumerate_configs
from harness.logger import engine_from_env, episodes_table
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

def completed(run_id):
    engine = engine_from_env()
    table = episodes_table(engine)
    stmt = select(table.c.config_hash).where(
        table.c.run_id == run_id, table.c.outcome.is_not(None))
    with engine.connect() as conn:
        return set(conn.execute(stmt).scalars().all())

if __name__ == "__main__":
    cfgs = configs()
    done = completed(RUN_ID)
    todo = [c for c in cfgs if c.config_hash not in done]
    print(f"{len(cfgs)} total, {len(done)} done, {len(todo)} remaining")
    run_batch(todo, run_id=RUN_ID,
              on_episode_end=lambda i, c, r: print(i, c.intensity, r["outcome"]))