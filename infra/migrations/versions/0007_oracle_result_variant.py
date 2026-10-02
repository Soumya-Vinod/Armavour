from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_oracle_result_variant"
down_revision = "0006_judge_model_code_sha"
branch_labels = None
depends_on = None


# All three columns are nullable with no server_default and no backfill (same
# reasoning as 0006): rows that predate this migration never stored the raw
# oracle payload, the testbed variant or the adapter's terminal reason, and
# NULL must stay distinguishable from a recorded value.
#   oracle_result   - window.__ARMAVOUR_RESULT__ exactly as the page set it
#                     (NULL = the oracle never fired; the legacy `outcome`
#                     column still scores that as avoided, scoring v2 does not)
#   testbed_variant - ARMAVOUR_TESTBED_VARIANT at run time (e.g. baseline/fixed)
#   terminal_reason - why the adapter stopped (explicit_done, step_cap, ...)
def upgrade() -> None:
    op.add_column("episodes", sa.Column("oracle_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("episodes", sa.Column("testbed_variant", sa.String(length=32), nullable=True))
    op.add_column("episodes", sa.Column("terminal_reason", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("episodes", "terminal_reason")
    op.drop_column("episodes", "testbed_variant")
    op.drop_column("episodes", "oracle_result")
