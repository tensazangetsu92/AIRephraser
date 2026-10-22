"""Set Robokassa as the default payment provider for new orders.

Revision ID: 20261022_0009
Revises: 20261020_0008
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20261022_0009"
down_revision = "20261020_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "provider",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="robokassa",
    )


def downgrade() -> None:
    op.alter_column(
        "payments",
        "provider",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="yookassa",
    )
