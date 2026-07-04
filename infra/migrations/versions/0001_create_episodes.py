from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_create_episodes"
down_revision = None
branch_labels = None
depends_on = None

outcome_enum = postgresql.ENUM("DC", "DF", "EC", "EF", name="episode_outcome", create_type=False)


def upgrade() -> None:
    outcome_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "episodes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("site", sa.String(length=64), nullable=False),
        sa.Column("pattern", sa.String(length=128), nullable=False),
        sa.Column("intensity", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("agent", sa.String(length=64), nullable=False),
        sa.Column("llm", sa.String(length=128), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("placed", sa.Boolean(), nullable=False),
        sa.Column("avoided", sa.Boolean(), nullable=True),
        sa.Column("outcome", outcome_enum, nullable=True),
        sa.Column("in_tokens", sa.Integer(), nullable=False),
        sa.Column("out_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("judge_flag", sa.Boolean(), nullable=True),
        sa.Column("judge_evidence", sa.Text(), nullable=True),
        sa.Column("trace", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_episodes_run_id", "episodes", ["run_id"])
    op.create_index("ix_episodes_pattern", "episodes", ["pattern"])


def downgrade() -> None:
    op.drop_index("ix_episodes_pattern", table_name="episodes")
    op.drop_index("ix_episodes_run_id", table_name="episodes")
    op.drop_table("episodes")
    outcome_enum.drop(op.get_bind(), checkfirst=True)
