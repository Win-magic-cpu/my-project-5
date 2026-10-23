"""init

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-23

建立对话状态表：一个用户一行，整份状态以 JSON 保存。
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dialogue_states",
        sa.Column("sender_id", sa.String(length=255), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("sender_id"),
    )


def downgrade() -> None:
    op.drop_table("dialogue_states")
