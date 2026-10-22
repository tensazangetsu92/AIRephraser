# app/database.py
from datetime import datetime, timedelta
import logging

from sqlalchemy import create_engine, Column, Integer, String, Text, LargeBinary, DateTime, Boolean, ForeignKey, Date, Index, JSON, Numeric, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy.sql import func
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
logger = logging.getLogger("uvicorn.error")


# Модели
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Email is optional for OAuth accounts whose provider does not disclose it.
    email = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    # Version and timestamp of the Terms/Privacy acknowledgement made before
    # the user completed any sign-in method.
    legal_documents_version = Column(String(32), nullable=True)
    legal_accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Связь с подпиской
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    oauth_identities = relationship("OAuthIdentity", back_populates="user")


class OAuthIdentity(Base):
    """Stable external identity used for passwordless OAuth-only accounts."""
    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_oauth_identities_provider_subject"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False)
    provider_subject = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="oauth_identities")


class UserHistory(Base):
    __tablename__ = "user_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tool_type = Column(String(50), default="humanizer")
    original_text = Column(Text, nullable=False)
    result_text = Column(Text, nullable=False)
    processing_options = Column(JSON, nullable=False, default=dict)
    processed_docx = Column(LargeBinary, nullable=True)
    processed_docx_filename = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    plan_type = Column(String(50), default="free")
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)
    payment_id = Column(String(255), nullable=True)
    # The free quota is a one-time onboarding entitlement. Paid and purchased
    # words remain available regardless of this flag.
    free_entitlement_available = Column(Boolean, nullable=False, default=True)

    last_reset_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="subscription")


class UsageStats(Base):
    """
    Одна запись на пользователя — суммарное количество слов,
    использованных в текущем расчётном периоде (месяце).
    Период начинается с last_reset_date подписки и обнуляется
    через reset_usage_stats при оплате или ежемесячном цикле.
    """
    __tablename__ = "usage_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    words_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")


class WordTransaction(Base):
    """Append-only word ledger; credit rows retain their unused balance."""
    __tablename__ = "word_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    operation_id = Column(String(36), nullable=False, index=True)
    kind = Column(String(16), nullable=False)  # credit or debit
    bucket = Column(String(24), nullable=False)  # bonus, purchased, subscription
    reason = Column(String(64), nullable=False)
    words = Column(Integer, nullable=False)
    remaining_words = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="confirmed")
    source_transaction_id = Column(Integer, ForeignKey("word_transactions.id"), nullable=True)
    payment_id = Column(String(255), nullable=True, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class Payment(Base):
    """Server-side payment order; only a verified provider status can fulfil it."""
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="robokassa")
    provider_payment_id = Column(String(255), unique=True, nullable=True)
    idempotence_key = Column(String(36), unique=True, nullable=False)
    product_type = Column(String(32), nullable=False)  # subscription or word_package
    product_id = Column(String(64), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="RUB")
    status = Column(String(32), nullable=False, default="created")
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")


class StudyWorkTrial(Base):
    """One free Study Work processing granted to each newly registered user."""
    __tablename__ = "study_work_trials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, default="available")  # available, processing, used
    reserved_at = Column(DateTime(timezone=True), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class UserProcessingLock(Base):
    """One active AI processing operation per user across all tools."""
    __tablename__ = "user_processing_locks"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    operation_id = Column(String(36), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class ApiRateLimit(Base):
    """Shared API rate-limit counter without storing raw IPs or emails."""
    __tablename__ = "api_rate_limits"

    key_hash = Column(String(64), primary_key=True)
    scope = Column(String(64), nullable=False)
    window_started_at = Column(DateTime(timezone=True), nullable=False)
    request_count = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserRefreshSession(Base):
    """Server-side, revocable persistent login session."""
    __tablename__ = "user_refresh_sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class PasswordResetCode(Base):
    """One-time password reset code. The code itself is never stored in the database."""
    __tablename__ = "password_reset_codes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class EmailLoginCode(Base):
    """One-time passwordless sign-in code; only its keyed hash is stored."""
    __tablename__ = "email_login_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DeletedAccountMarker(Base):
    """Pseudonymous marker preventing a repeated free grant after deletion.

    It deliberately stores no email, text, document, session, or account id.
    The marker is a keyed HMAC calculated only while a user proves control of
    the email again, and expires after the documented retention period.
    """
    __tablename__ = "deleted_account_markers"

    email_hmac = Column(String(64), primary_key=True)
    deleted_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


# Composite indexes for the filters used by the most frequent production requests.
QUERY_INDEXES = (
    Index("ix_user_history_created_at", UserHistory.created_at),
    Index("ix_user_history_user_created_at", UserHistory.user_id, UserHistory.created_at),
    Index("ix_user_history_user_tool_created_at", UserHistory.user_id, UserHistory.tool_type, UserHistory.created_at),
    Index(
        "ix_word_transactions_balance_lookup",
        WordTransaction.user_id,
        WordTransaction.kind,
        WordTransaction.status,
        WordTransaction.bucket,
    ),
    Index("ix_payments_user_status", Payment.user_id, Payment.status),
    Index("ix_api_rate_limits_scope", ApiRateLimit.scope),
    Index("ix_user_refresh_sessions_user_revoked", UserRefreshSession.user_id, UserRefreshSession.revoked_at),
    Index("ix_password_reset_codes_user_used_expires", PasswordResetCode.user_id, PasswordResetCode.used_at, PasswordResetCode.expires_at),
    Index("ix_email_login_codes_email_used_expires", EmailLoginCode.email, EmailLoginCode.used_at, EmailLoginCode.expires_at),
    Index("ix_deleted_account_markers_expires_at", DeletedAccountMarker.expires_at),
    Index("ix_oauth_identities_user_id", OAuthIdentity.user_id),
)


def delete_old_history(db: Session, days: int = 90):
    """Удаляет записи истории старше N дней"""
    cutoff_date = datetime.now() - timedelta(days=days)
    deleted = db.query(UserHistory).filter(
        UserHistory.created_at < cutoff_date
    ).delete()
    db.commit()
    if deleted:
        logger.info("Removed %s history records older than %s days", deleted, days)
    return deleted


# Зависимости для FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
