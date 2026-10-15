"""Add shared API rate-limit counters.

Revision ID: 20260928_0002
Revises: 20260928_0001
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260928_0002"
down_revision = "20260928_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_rate_limits",
        sa.Column("key_hash", sa.String(length=64), primary_key=True),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("ix_api_rate_limits_expires_at", "api_rate_limits", ["expires_at"])
    op.create_index("ix_api_rate_limits_scope", "api_rate_limits", ["scope"])


def downgrade() -> None:
    op.drop_table("api_rate_limits")
