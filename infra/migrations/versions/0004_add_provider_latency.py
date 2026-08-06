from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_add_provider_latency"
down_revision = "0003_add_duration_seconds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "episodes",
        sa.Column("provider_latency_seconds", sa.Numeric(precision=10, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("episodes", "provider_latency_seconds")
