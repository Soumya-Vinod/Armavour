from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine


def engine_from_env() -> Engine:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return create_engine(database_url)


def episodes_table(engine: Engine) -> Table:
    metadata = MetaData()
    return Table("episodes", metadata, autoload_with=engine)


def log_episode(row: dict[str, Any], *, engine: Engine | None = None, table: Table | None = None) -> None:
    engine = engine or engine_from_env()
    table = table or episodes_table(engine)
    payload = _normalise_row(row)
    insert_fn = sqlite_insert if engine.dialect.name == "sqlite" else pg_insert
    insert_stmt = insert_fn(table).values(payload)
    update_values = {
        column.name: insert_stmt.excluded[column.name]
        for column in table.columns
        if column.name not in {"id", "created_at"}
    }
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["config_hash", "run_id"],
        set_=update_values,
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def _normalise_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    cost = payload.get("cost_usd")
    if cost is not None and not isinstance(cost, Decimal):
        payload["cost_usd"] = Decimal(str(cost))
    return payload
