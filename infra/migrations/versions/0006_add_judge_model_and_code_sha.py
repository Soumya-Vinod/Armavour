from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_judge_model_code_sha"
down_revision = "0005_add_instruction_language"
branch_labels = None
depends_on = None


# Both columns are nullable with no server_default and no backfill: rows that
# predate this migration genuinely have no recorded judge model or code commit,
# and NULL must stay distinguishable from a real value (cf. 0005's 'en' default,
# which relabels pre-existing hi/hinglish rows if applied to old data).
def upgrade() -> None:
    op.add_column("episodes", sa.Column("judge_model", sa.String(length=128), nullable=True))
    op.add_column("episodes", sa.Column("code_sha", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("episodes", "code_sha")
    op.drop_column("episodes", "judge_model")
