"""Create the initial Humary schema.

Revision ID: 20260928_0001
Revises:
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260928_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    timestamp = sa.text("CURRENT_TIMESTAMP")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=True),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tool_type", sa.String(length=50), server_default="humanizer", nullable=True),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("result_text", sa.Text(), nullable=False),
        sa.Column("processed_docx", sa.LargeBinary(), nullable=True),
        sa.Column("processed_docx_filename", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_user_history_id", "user_history", ["id"])
    op.create_index("ix_user_history_created_at", "user_history", ["created_at"])
    op.create_index("ix_user_history_user_created_at", "user_history", ["user_id", "created_at"])
    op.create_index("ix_user_history_user_tool_created_at", "user_history", ["user_id", "tool_type", "created_at"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("plan_type", sa.String(length=50), server_default="free", nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_id", sa.String(length=255), nullable=True),
        sa.Column("last_reset_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_subscriptions_id", "subscriptions", ["id"])

    op.create_table(
        "usage_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("words_used", sa.Integer(), server_default="0", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_usage_stats_id", "usage_stats", ["id"])

    op.create_table(
        "word_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("bucket", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("words", sa.Integer(), nullable=False),
        sa.Column("remaining_words", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="confirmed", nullable=False),
        sa.Column("source_transaction_id", sa.Integer(), nullable=True),
        sa.Column("payment_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_transaction_id"], ["word_transactions.id"]),
    )
    op.create_index("ix_word_transactions_id", "word_transactions", ["id"])
    op.create_index("ix_word_transactions_user_id", "word_transactions", ["user_id"])
    op.create_index("ix_word_transactions_operation_id", "word_transactions", ["operation_id"])
    op.create_index("ix_word_transactions_balance_lookup", "word_transactions", ["user_id", "kind", "status", "bucket"])

    op.create_table(
        "study_work_trials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="available", nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_study_work_trials_id", "study_work_trials", ["id"])
    op.create_index("ix_study_work_trials_user_id", "study_work_trials", ["user_id"], unique=True)

    op.create_table(
        "user_processing_locks",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_user_processing_locks_expires_at", "user_processing_locks", ["expires_at"])

    op.create_table(
        "user_refresh_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_user_refresh_sessions_user_id", "user_refresh_sessions", ["user_id"])
    op.create_index("ix_user_refresh_sessions_token_hash", "user_refresh_sessions", ["token_hash"], unique=True)
    op.create_index("ix_user_refresh_sessions_last_used_at", "user_refresh_sessions", ["last_used_at"])
    op.create_index("ix_user_refresh_sessions_expires_at", "user_refresh_sessions", ["expires_at"])
    op.create_index("ix_user_refresh_sessions_revoked_at", "user_refresh_sessions", ["revoked_at"])
    op.create_index("ix_user_refresh_sessions_user_revoked", "user_refresh_sessions", ["user_id", "revoked_at"])

    op.create_table(
        "password_reset_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_password_reset_codes_id", "password_reset_codes", ["id"])
    op.create_index("ix_password_reset_codes_user_id", "password_reset_codes", ["user_id"])
    op.create_index("ix_password_reset_codes_expires_at", "password_reset_codes", ["expires_at"])
    op.create_index("ix_password_reset_codes_used_at", "password_reset_codes", ["used_at"])
    op.create_index("ix_password_reset_codes_user_used_expires", "password_reset_codes", ["user_id", "used_at", "expires_at"])


def downgrade() -> None:
    op.drop_table("password_reset_codes")
    op.drop_table("user_refresh_sessions")
    op.drop_table("user_processing_locks")
    op.drop_table("study_work_trials")
    op.drop_table("word_transactions")
    op.drop_table("usage_stats")
    op.drop_table("subscriptions")
    op.drop_table("user_history")
    op.drop_table("users")
