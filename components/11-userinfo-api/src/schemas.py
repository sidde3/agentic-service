"""
Pydantic V2 Schemas for FastAPI

Maps to existing PostgreSQL database structure.
Uses from_attributes for ORM integration.
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict, Field


# ==================== User Schemas ====================

class UserBase(BaseModel):
    """Base user schema with common fields."""
    username: str = Field(..., min_length=1, max_length=50)
    user_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    external_id: Optional[str] = Field(None, max_length=50)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    pass


class UserUpdate(BaseModel):
    """Schema for updating user details (all fields optional)."""
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    user_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    external_id: Optional[str] = Field(None, max_length=50)


class UserResponse(UserBase):
    """Response schema for user with ORM mapping."""
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserWithSubscriptionsResponse(UserResponse):
    """User response with subscriptions."""
    subscriptions: List["SubscriptionResponse"] = []

    model_config = ConfigDict(from_attributes=True)


# ==================== Subscription Schemas ====================

class SubscriptionBase(BaseModel):
    """Base subscription schema."""
    mobile_number: str = Field(..., max_length=20)
    account_number: str = Field(..., max_length=50)
    status: str = Field(default="active", max_length=20)


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a subscription."""
    user_id: int


class SubscriptionStatusUpdate(BaseModel):
    """Schema for updating subscription status."""
    status: str = Field(..., pattern="^(active|suspended|cancelled)$")


class SubscriptionResponse(SubscriptionBase):
    """Response schema for subscription."""
    subscription_id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== Plan Schemas ====================

class PlanBase(BaseModel):
    """Base plan schema."""
    plan_name: str = Field(..., max_length=100)
    data_limit_gb: int = Field(..., ge=0)
    voice_limit_minutes: int = Field(..., ge=0)
    sms_limit: int = Field(..., ge=0)
    price: float = Field(..., ge=0)


class PlanCreate(PlanBase):
    """Schema for creating a plan."""
    pass


class PlanResponse(PlanBase):
    """Response schema for plan."""
    plan_id: int

    model_config = ConfigDict(from_attributes=True)


# ==================== User Plan Schemas ====================

class UserPlanBase(BaseModel):
    """Base user plan schema."""
    plan_id: int
    start_date: date
    end_date: date


class UserPlanCreate(BaseModel):
    """Schema for assigning a plan to subscription."""
    plan_id: int
    start_date: Optional[date] = None  # Defaults to today if not provided


class UserPlanResponse(UserPlanBase):
    """Response schema for user plan."""
    id: int
    subscription_id: int

    model_config = ConfigDict(from_attributes=True)


class UserPlanWithDetailsResponse(UserPlanResponse):
    """User plan response with plan details."""
    plan: PlanResponse

    model_config = ConfigDict(from_attributes=True)


# ==================== Usage Record Schemas ====================

class UsageRecordBase(BaseModel):
    """Base usage record schema."""
    usage_date: date
    data_used_gb: float = Field(..., ge=0)
    voice_used_minutes: int = Field(..., ge=0)
    sms_used: int = Field(..., ge=0)


class UsageRecordCreate(UsageRecordBase):
    """Schema for creating/upserting usage record."""
    pass


class UsageRecordResponse(UsageRecordBase):
    """Response schema for usage record."""
    usage_id: int
    subscription_id: int

    model_config = ConfigDict(from_attributes=True)


class UsageAggregateResponse(BaseModel):
    """Response schema for aggregated usage."""
    subscription_id: int
    start_date: date
    end_date: date
    total_data_gb: float
    total_voice_minutes: int
    total_sms: int
    record_count: int

    model_config = ConfigDict(from_attributes=True)


# ==================== Billing Schemas ====================

class BillingBase(BaseModel):
    """Base billing schema."""
    billing_cycle_start: date
    billing_cycle_end: date
    total_amount: float = Field(..., ge=0)


class BillingCreate(BaseModel):
    """Schema for creating a bill."""
    billing_cycle_start: date
    billing_cycle_end: date
    # total_amount calculated from plan + overage


class BillingResponse(BillingBase):
    """Response schema for billing."""
    bill_id: int
    subscription_id: int
    paid: bool
    payment_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class BillingPaymentUpdate(BaseModel):
    """Schema for marking bill as paid."""
    payment_date: Optional[date] = None  # Defaults to today if not provided


# ==================== Usage Insight Schemas ====================

class UsageInsightBase(BaseModel):
    """Base usage insight schema."""
    month: date
    usage_type: str = Field(..., max_length=20)
    data_usage_percent: float = Field(..., ge=0, le=100)


class UsageInsightCreate(UsageInsightBase):
    """Schema for creating usage insight."""
    subscription_id: int


class UsageInsightResponse(UsageInsightBase):
    """Response schema for usage insight."""
    id: int
    subscription_id: int

    model_config = ConfigDict(from_attributes=True)


# ==================== Pagination Schemas ====================

class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    total: int
    page: int
    page_size: int
    items: List[BaseModel]


class PaginatedUsersResponse(BaseModel):
    """Paginated users response."""
    total: int
    page: int
    page_size: int
    items: List[UserResponse]


class PaginatedSubscriptionsResponse(BaseModel):
    """Paginated subscriptions response."""
    total: int
    page: int
    page_size: int
    items: List[SubscriptionResponse]


class PaginatedPlansResponse(BaseModel):
    """Paginated plans response."""
    total: int
    page: int
    page_size: int
    items: List[PlanResponse]
