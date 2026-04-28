"""
User Plans API Router

Endpoints:
- POST /subscriptions/{subscription_id}/plans - Assign a plan to a subscription
- GET /subscriptions/{subscription_id}/plans - Get plans for a subscription
"""

from datetime import date, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import UserPlan, Subscription, Plan
from ..schemas import (
    UserPlanCreate,
    UserPlanWithDetailsResponse,
)

router = APIRouter(tags=["User Plans"])


@router.post(
    "/subscriptions/{subscription_id}/plans",
    response_model=UserPlanWithDetailsResponse,
    status_code=201
)
async def assign_plan(
    subscription_id: int,
    plan_data: UserPlanCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Assign a plan to a subscription.

    Creates a new user_plan entry linking the subscription to a plan
    with start and end dates.

    Raises:
    - 404 Not Found: If subscription or plan doesn't exist
    """
    subscription = await db.scalar(
        select(Subscription).where(Subscription.subscription_id == subscription_id)
    )
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=f"Subscription {subscription_id} not found"
        )

    plan = await db.scalar(
        select(Plan).where(Plan.plan_id == plan_data.plan_id)
    )
    if not plan:
        raise HTTPException(
            status_code=404,
            detail=f"Plan {plan_data.plan_id} not found"
        )

    start_date = plan_data.start_date if plan_data.start_date else date.today()
    end_date = start_date + timedelta(days=30)

    user_plan = UserPlan(
        subscription_id=subscription_id,
        plan_id=plan_data.plan_id,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(user_plan)
    await db.flush()
    await db.refresh(user_plan)

    result = await db.execute(
        select(UserPlan)
        .where(UserPlan.id == user_plan.id)
        .options(selectinload(UserPlan.plan))
    )
    user_plan_with_details = result.scalar_one()

    return UserPlanWithDetailsResponse.model_validate(user_plan_with_details)


@router.get(
    "/subscriptions/{subscription_id}/plans",
    response_model=List[UserPlanWithDetailsResponse]
)
async def get_subscription_plans(
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all plans (current and historical) for a subscription.

    Returns plans ordered by start_date descending (most recent first).

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

    result = await db.execute(
        select(UserPlan)
        .where(UserPlan.subscription_id == subscription_id)
        .options(selectinload(UserPlan.plan))
        .order_by(UserPlan.start_date.desc())
    )
    user_plans = result.scalars().all()

    return [UserPlanWithDetailsResponse.model_validate(up) for up in user_plans]
