# app/database.py
from datetime import datetime, timedelta

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
from fastapi import Depends
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Модели
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Связь с подпиской
    subscription = relationship("Subscription", back_populates="user", uselist=False)


class UserHistory(Base):
    __tablename__ = "user_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tool_type = Column(String(50), default="humanizer")
    original_text = Column(Text, nullable=False)
    result_text = Column(Text, nullable=False)
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


def delete_old_history(db: Session, days: int = 90):
    """Удаляет записи истории старше N дней"""
    cutoff_date = datetime.now() - timedelta(days=days)
    deleted = db.query(UserHistory).filter(
        UserHistory.created_at < cutoff_date
    ).delete()
    db.commit()
    if deleted:
        print(f"🗑️ Удалено {deleted} старых записей из истории (старше {days} дней)")
    return deleted


# Зависимости для FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Создание таблиц
def create_tables():
    Base.metadata.create_all(bind=engine)