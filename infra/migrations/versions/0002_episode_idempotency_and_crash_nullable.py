from __future__ import annotations

from alembic import op

revision = "0002_idempot_crash_null"
down_revision = "0001_create_episodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("episodes", "placed", nullable=True)
    op.drop_constraint("episodes_config_hash_key", "episodes", type_="unique")
    op.create_unique_constraint(
        "uq_episodes_config_hash_run_id",
        "episodes",
        ["config_hash", "run_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_episodes_config_hash_run_id", "episodes", type_="unique")
    op.create_unique_constraint("episodes_config_hash_key", "episodes", ["config_hash"])
    op.alter_column("episodes", "placed", nullable=False)
