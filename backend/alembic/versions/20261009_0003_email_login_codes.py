"""Add persistent one-time codes for passwordless email sign-in.

Revision ID: 20261009_0003
Revises: 20260928_0002
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20261009_0003"
down_revision = "20260928_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_login_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
    )
    op.create_index("ix_email_login_codes_email", "email_login_codes", ["email"])
    op.create_index("ix_email_login_codes_expires_at", "email_login_codes", ["expires_at"])
    op.create_index("ix_email_login_codes_used_at", "email_login_codes", ["used_at"])
    op.create_index(
        "ix_email_login_codes_email_used_expires",
        "email_login_codes",
        ["email", "used_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("email_login_codes")
