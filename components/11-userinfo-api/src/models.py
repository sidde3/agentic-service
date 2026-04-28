"""
SQLAlchemy 2.0 Models

Maps to existing PostgreSQL database structure.
DO NOT generate migrations - these tables already exist.
"""

from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Numeric, Date, DateTime, Boolean, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """Users table - stores user account information."""
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="user")


class Subscription(Base):
    """Subscriptions table - mobile lines owned by users."""
    __tablename__ = "subscriptions"

    subscription_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    mobile_number: Mapped[str] = mapped_column(String(20), unique=True)
    account_number: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscriptions")
    user_plans: Mapped[List["UserPlan"]] = relationship(back_populates="subscription")
    usage_records: Mapped[List["UsageRecord"]] = relationship(back_populates="subscription")
    bills: Mapped[List["Billing"]] = relationship(back_populates="subscription")
    insights: Mapped[List["UsageInsight"]] = relationship(back_populates="subscription")


class Plan(Base):
    """Plans table - mobile plan catalog."""
    __tablename__ = "plans"

    plan_id: Mapped[int] = mapped_column(primary_key=True)
    plan_name: Mapped[str] = mapped_column(String(100), unique=True)
    data_limit_gb: Mapped[int] = mapped_column(Integer)
    voice_limit_minutes: Mapped[int] = mapped_column(Integer)
    sms_limit: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(10, 2))

    # Relationships
    user_plans: Mapped[List["UserPlan"]] = relationship(back_populates="plan")


class UserPlan(Base):
    """User plans table - tracks which plan a subscription has over time."""
    __tablename__ = "user_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.subscription_id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.plan_id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    # Relationships
    subscription: Mapped["Subscription"] = relationship(back_populates="user_plans")
    plan: Mapped["Plan"] = relationship(back_populates="user_plans")


class UsageRecord(Base):
    """Usage records table - daily usage logs."""
    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint('subscription_id', 'usage_date', name='uq_subscription_usage_date'),
    )

    usage_id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.subscription_id"))
    usage_date: Mapped[date] = mapped_column(Date)
    data_used_gb: Mapped[float] = mapped_column(Numeric(5, 2))
    voice_used_minutes: Mapped[int] = mapped_column(Integer)
    sms_used: Mapped[int] = mapped_column(Integer)

    # Relationships
    subscription: Mapped["Subscription"] = relationship(back_populates="usage_records")


class Billing(Base):
    """Billing table - stores bills for subscriptions."""
    __tablename__ = "billing"

    bill_id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.subscription_id"))
    billing_cycle_start: Mapped[date] = mapped_column(Date)
    billing_cycle_end: Mapped[date] = mapped_column(Date)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    paid: Mapped[bool] = mapped_column(Boolean, server_default="false")
    payment_date: Mapped[Optional[date]] = mapped_column(Date)

    # Relationships
    subscription: Mapped["Subscription"] = relationship(back_populates="bills")


class UsageInsight(Base):
    """Usage insights table - monthly usage analytics."""
    __tablename__ = "usage_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.subscription_id"))
    month: Mapped[date] = mapped_column(Date)
    usage_type: Mapped[str] = mapped_column(String(20))
    data_usage_percent: Mapped[float] = mapped_column(Numeric(5, 2))

    # Relationships
    subscription: Mapped["Subscription"] = relationship(back_populates="insights")
