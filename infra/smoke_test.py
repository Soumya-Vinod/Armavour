from __future__ import annotations

import os
import uuid
from decimal import Decimal

from sqlalchemy import MetaData, Table, create_engine, insert, select


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    engine = create_engine(database_url)
    metadata = MetaData()
    episodes = Table("episodes", metadata, autoload_with=engine)

    marker = uuid.uuid4().hex
    row = {
        "run_id": f"smoke-{marker}",
        "config_hash": f"smoke-{marker}",
        "site": "spike",
        "pattern": "basket_sneaking",
        "intensity": "low",
        "language": "en",
        "agent": "smoke",
        "llm": "none",
        "seed": 0,
        "placed": True,
        "avoided": True,
        "outcome": "EC",
        "in_tokens": 0,
        "out_tokens": 0,
        "cost_usd": Decimal("0.000000"),
        "steps": 0,
        "judge_flag": None,
        "judge_evidence": None,
        "trace": [{"step": 0, "reasoning": "smoke test placeholder"}],
    }

    with engine.begin() as conn:
        result = conn.execute(insert(episodes).values(row).returning(episodes.c.id))
        episode_id = result.scalar_one()
        selected = conn.execute(select(episodes).where(episodes.c.id == episode_id)).mappings().one()

    print(
        "PASS - smoke row round-tripped:",
        selected["id"],
        selected["run_id"],
        selected["outcome"],
    )


if __name__ == "__main__":
    main()
