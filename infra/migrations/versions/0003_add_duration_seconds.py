from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_add_duration_seconds"
down_revision = "0002_idempot_crash_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "episodes",
        sa.Column("duration_seconds", sa.Numeric(precision=10, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("episodes", "duration_seconds")
