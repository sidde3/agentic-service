"""
Usage API Router

Endpoints:
- POST /subscriptions/{subscription_id}/usage - Upsert daily usage
- GET /subscriptions/{subscription_id}/usage - List usage records
- GET /subscriptions/{subscription_id}/usage/aggregate - Aggregate usage over date range
"""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from ..database import get_db
from ..models import UsageRecord, Subscription
from ..schemas import (
    UsageRecordCreate,
    UsageRecordResponse,
    UsageAggregateResponse,
)

router = APIRouter(tags=["Usage"])


@router.post(
    "/subscriptions/{subscription_id}/usage",
    response_model=UsageRecordResponse,
    status_code=201
)
async def upsert_usage(
    subscription_id: int,
    usage_data: UsageRecordCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Upsert daily usage record.

    If a record for the same subscription_id and usage_date exists,
    it will be updated. Otherwise, a new record is created.

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

    stmt = insert(UsageRecord).values(
        subscription_id=subscription_id,
        **usage_data.model_dump()
    ).on_conflict_do_update(
        index_elements=['subscription_id', 'usage_date'],
        set_={
            'data_used_gb': usage_data.data_used_gb,
            'voice_used_minutes': usage_data.voice_used_minutes,
            'sms_used': usage_data.sms_used,
        }
    ).returning(UsageRecord)

    result = await db.execute(stmt)
    await db.flush()
    usage_record = result.scalar_one()

    await db.refresh(usage_record)

    return UsageRecordResponse.model_validate(usage_record)


@router.get(
    "/subscriptions/{subscription_id}/usage",
    response_model=List[UsageRecordResponse]
)
async def list_usage(
    subscription_id: int,
    start_date: Optional[date] = Query(None, description="Filter start date"),
    end_date: Optional[date] = Query(None, description="Filter end date"),
    db: AsyncSession = Depends(get_db),
):
    """
    List usage records for a subscription.

    Query Parameters:
    - start_date: Filter records from this date (inclusive, optional)
    - end_date: Filter records up to this date (inclusive, optional)

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

    query = select(UsageRecord).where(
        UsageRecord.subscription_id == subscription_id
    )

    if start_date:
        query = query.where(UsageRecord.usage_date >= start_date)
    if end_date:
        query = query.where(UsageRecord.usage_date <= end_date)

    query = query.order_by(UsageRecord.usage_date.desc())

    result = await db.execute(query)
    usage_records = result.scalars().all()

    return [UsageRecordResponse.model_validate(record) for record in usage_records]


@router.get(
    "/subscriptions/{subscription_id}/usage/aggregate",
    response_model=UsageAggregateResponse
)
async def aggregate_usage(
    subscription_id: int,
    start_date: date = Query(..., description="Aggregation start date"),
    end_date: date = Query(..., description="Aggregation end date"),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregate usage over a date range.

    Sums data_used_gb, voice_used_minutes, sms_used over the specified range.

    Query Parameters:
    - start_date: Start date (inclusive, required)
    - end_date: End date (inclusive, required)

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
        select(
            func.sum(UsageRecord.data_used_gb).label('total_data_gb'),
            func.sum(UsageRecord.voice_used_minutes).label('total_voice_minutes'),
            func.sum(UsageRecord.sms_used).label('total_sms'),
            func.count(UsageRecord.usage_id).label('record_count'),
        )
        .where(UsageRecord.subscription_id == subscription_id)
        .where(UsageRecord.usage_date >= start_date)
        .where(UsageRecord.usage_date <= end_date)
    )
    row = result.one()

    return UsageAggregateResponse(
        subscription_id=subscription_id,
        start_date=start_date,
        end_date=end_date,
        total_data_gb=float(row.total_data_gb or 0),
        total_voice_minutes=int(row.total_voice_minutes or 0),
        total_sms=int(row.total_sms or 0),
        record_count=int(row.record_count or 0),
    )
