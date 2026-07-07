from __future__ import annotations

from decimal import Decimal

import pytest

sa = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, select  # noqa: E402

from harness.logger import log_episode  # noqa: E402


def test_log_episode_upserts_on_config_hash_and_run_id() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    episodes = sa.Table(
        "episodes",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("config_hash", sa.String(), nullable=False),
        sa.Column("site", sa.String(), nullable=False),
        sa.Column("pattern", sa.String(), nullable=False),
        sa.Column("intensity", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("agent", sa.String(), nullable=False),
        sa.Column("llm", sa.String(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("placed", sa.Boolean(), nullable=True),
        sa.Column("avoided", sa.Boolean(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("in_tokens", sa.Integer(), nullable=False),
        sa.Column("out_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("judge_flag", sa.Boolean(), nullable=True),
        sa.Column("judge_evidence", sa.Text(), nullable=True),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("config_hash", "run_id"),
    )
    metadata.create_all(engine)

    row = episode_row(outcome="DC", avoided=False)
    log_episode(row, engine=engine, table=episodes)
    log_episode({**row, "outcome": "EC", "avoided": True}, engine=engine, table=episodes)

    with engine.begin() as conn:
        rows = conn.execute(select(episodes)).mappings().all()

    assert len(rows) == 1
    assert rows[0]["outcome"] == "EC"
    assert rows[0]["avoided"] is True


def episode_row(*, outcome: str, avoided: bool) -> dict[str, object]:
    return {
        "run_id": "run-1",
        "config_hash": "hash-1",
        "site": "ticketing",
        "pattern": "basket_sneaking",
        "intensity": "moderate",
        "language": "en",
        "agent": "computeruse",
        "llm": "model",
        "seed": 0,
        "placed": True,
        "avoided": avoided,
        "outcome": outcome,
        "in_tokens": 1,
        "out_tokens": 2,
        "cost_usd": Decimal("0.000033"),
        "steps": 1,
        "judge_flag": None,
        "judge_evidence": None,
        "trace": [{"step": 0}],
    }
