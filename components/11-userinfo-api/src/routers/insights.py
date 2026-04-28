"""
Usage Insights API Router

Endpoints:
- POST /subscriptions/{subscription_id}/insights - Create usage insight
- GET /subscriptions/{subscription_id}/insights - List usage insights
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import UsageInsight, Subscription
from ..schemas import (
    UsageInsightCreate,
    UsageInsightResponse,
)

router = APIRouter(tags=["Usage Insights"])


@router.post(
    "/subscriptions/{subscription_id}/insights",
    response_model=UsageInsightResponse,
    status_code=201
)
async def create_insight(
    subscription_id: int,
    insight_data: UsageInsightCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a usage insight for a subscription.

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

    if insight_data.subscription_id != subscription_id:
        raise HTTPException(
            status_code=400,
            detail=f"Subscription ID mismatch: path={subscription_id}, body={insight_data.subscription_id}"
        )

    insight = UsageInsight(**insight_data.model_dump())
    db.add(insight)
    await db.flush()
    await db.refresh(insight)

    return UsageInsightResponse.model_validate(insight)


@router.get(
    "/subscriptions/{subscription_id}/insights",
    response_model=List[UsageInsightResponse]
)
async def list_insights(
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    List all usage insights for a subscription.

    Returns insights ordered by month descending.

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
        select(UsageInsight)
        .where(UsageInsight.subscription_id == subscription_id)
        .order_by(UsageInsight.month.desc())
    )
    insights = result.scalars().all()

    return [UsageInsightResponse.model_validate(insight) for insight in insights]
