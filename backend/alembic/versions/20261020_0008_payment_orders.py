"""Add server-side payment orders for verified YooKassa fulfilment.

Revision ID: 20261020_0008
Revises: 20261019_0007
Create Date: 2026-10-20
"""

from alembic import op
import sqlalchemy as sa


revision = "20261020_0008"
down_revision = "20261019_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="yookassa"),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("idempotence_key", sa.String(length=36), nullable=False),
        sa.Column("product_type", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotence_key"),
        sa.UniqueConstraint("provider_payment_id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_user_status", "payments", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_payments_user_status", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
