"""Keep a finite pseudonymous marker after account deletion.

Revision ID: 20261018_0005
Revises: 20261018_0004
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20261018_0005"
down_revision = "20261018_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column(
            "free_entitlement_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_table(
        "deleted_account_markers",
        sa.Column("email_hmac", sa.String(length=64), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_deleted_account_markers_expires_at",
        "deleted_account_markers",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_deleted_account_markers_expires_at", table_name="deleted_account_markers")
    op.drop_table("deleted_account_markers")
    op.drop_column("subscriptions", "free_entitlement_available")
