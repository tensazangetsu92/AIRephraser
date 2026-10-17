"""Store selected processing options with every history record.

Revision ID: 20261018_0004
Revises: 20261009_0003
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20261018_0004"
down_revision = "20261009_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_history",
        sa.Column(
            "processing_options",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_history", "processing_options")
