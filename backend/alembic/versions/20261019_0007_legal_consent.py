"""Record the accepted Terms and Privacy document version for each user.

Revision ID: 20261019_0007
Revises: 20261018_0006
Create Date: 2026-10-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20261019_0007"
down_revision = "20261018_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("legal_documents_version", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("legal_accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "legal_accepted_at")
    op.drop_column("users", "legal_documents_version")
