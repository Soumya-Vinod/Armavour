from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_add_instruction_language"
down_revision = "0004_add_provider_latency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "episodes",
        sa.Column("instruction_language", sa.String(length=32), server_default="en", nullable=False),
    )
    op.add_column(
        "episodes",
        sa.Column("ui_language", sa.String(length=32), server_default="en", nullable=True),
    )
    op.add_column(
        "episodes",
        sa.Column("instruction_prompt", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("episodes", "instruction_prompt")
    op.drop_column("episodes", "ui_language")
    op.drop_column("episodes", "instruction_language")
