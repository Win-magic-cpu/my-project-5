"""add state version and updated_at

Revision ID: 0002_state_version
Revises: 0001_initial
Create Date: 2026-10-23

为对话状态增加乐观锁版本号与更新时间：
- version 每次成功保存 +1，写入时用它做条件更新；
- updated_at 便于排查"这条状态最后一次变更是什么时候"。
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_state_version"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dialogue_states",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "dialogue_states",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("dialogue_states", "updated_at")
    op.drop_column("dialogue_states", "version")
