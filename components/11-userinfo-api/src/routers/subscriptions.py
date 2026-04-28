"""
Subscriptions API Router

Endpoints:
- GET /subscriptions - List subscriptions with pagination and filters
- POST /subscriptions - Create a subscription
- GET /subscriptions/{subscription_id} - Get a subscription
- PATCH /subscriptions/{subscription_id}/status - Update subscription status
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Subscription, User
from ..schemas import (
    SubscriptionCreate,
    SubscriptionStatusUpdate,
    SubscriptionResponse,
    PaginatedSubscriptionsResponse,
)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("", response_model=PaginatedSubscriptionsResponse)
async def list_subscriptions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user_id: Optional[int] = Query(None, description="Filter by user_id"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
):
    """
    List subscriptions with pagination and optional filters.

    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - user_id: Filter by user_id (optional)
    - status: Filter by status (optional)
    """
    query = select(Subscription)

    if user_id:
        query = query.where(Subscription.user_id == user_id)
    if status:
        query = query.where(Subscription.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    subscriptions = result.scalars().all()

    return PaginatedSubscriptionsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[SubscriptionResponse.model_validate(sub) for sub in subscriptions],
    )


@router.post("", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new subscription.

    Raises:
    - 404 Not Found: If user doesn't exist
    - 409 Conflict: If mobile_number already exists
    """
    user = await db.scalar(
        select(User).where(User.user_id == subscription_data.user_id)
    )
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User {subscription_data.user_id} not found"
        )

    existing = await db.scalar(
        select(Subscription).where(
            Subscription.mobile_number == subscription_data.mobile_number
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Mobile number '{subscription_data.mobile_number}' already exists"
        )

    subscription = Subscription(**subscription_data.model_dump())
    db.add(subscription)
    await db.flush()
    await db.refresh(subscription)

    return SubscriptionResponse.model_validate(subscription)


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get subscription by ID.

    Raises:
    - 404 Not Found: If subscription doesn't exist
    """
    subscription = await db.scalar(
        select(Subscription).where(Subscription.subscription_id == subscription_id)
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=f"Subscription {subscription_id} not found"
        )

    return SubscriptionResponse.model_validate(subscription)


@router.patch("/{subscription_id}/status", response_model=SubscriptionResponse)
async def update_subscription_status(
    subscription_id: int,
    status_update: SubscriptionStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update subscription status.

    Valid statuses: active, suspended, cancelled

    Raises:
    - 404 Not Found: If subscription doesn't exist
    """
    subscription = await db.scalar(
        select(Subscription).where(Subscription.subscription_id == subscription_id)
    )

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=f"Subscription {subscription_id} not found"
        )

    subscription.status = status_update.status
    await db.flush()
    await db.refresh(subscription)

    return SubscriptionResponse.model_validate(subscription)
