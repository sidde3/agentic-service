"""
Billing API Router

Endpoints:
- POST /subscriptions/{subscription_id}/bills - Create a bill
- GET /subscriptions/{subscription_id}/bills - List bills
- GET /subscriptions/{subscription_id}/bills/{bill_id} - Get a bill
- POST /subscriptions/{subscription_id}/bills/{bill_id}/pay - Mark bill as paid
"""

from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Billing, Subscription, UserPlan, Plan, UsageRecord
from ..schemas import (
    BillingCreate,
    BillingResponse,
    BillingPaymentUpdate,
)

router = APIRouter(tags=["Billing"])


@router.post(
    "/subscriptions/{subscription_id}/bills",
    response_model=BillingResponse,
    status_code=201
)
async def create_bill(
    subscription_id: int,
    bill_data: BillingCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a bill for a subscription.

    Calculates total_amount based on the plan price during the billing cycle.

    Raises:
    - 404 Not Found: If subscription doesn't exist or no plan found for the period
    """
    subscription = await db.scalar(
        select(Subscription).where(Subscription.subscription_id == subscription_id)
    )
    if not subscription:
        raise HTTPException(
            status_code=404,
            detail=f"Subscription {subscription_id} not found"
        )

    user_plan = await db.scalar(
        select(UserPlan)
        .where(UserPlan.subscription_id == subscription_id)
        .where(UserPlan.start_date <= bill_data.billing_cycle_end)
        .where(UserPlan.end_date >= bill_data.billing_cycle_start)
        .limit(1)
    )

    if not user_plan:
        raise HTTPException(
            status_code=404,
            detail=f"No plan found for subscription {subscription_id} during billing period"
        )

    plan = await db.scalar(
        select(Plan).where(Plan.plan_id == user_plan.plan_id)
    )

    total_amount = float(plan.price)

    bill = Billing(
        subscription_id=subscription_id,
        billing_cycle_start=bill_data.billing_cycle_start,
        billing_cycle_end=bill_data.billing_cycle_end,
        total_amount=total_amount,
        paid=False,
    )
    db.add(bill)
    await db.flush()
    await db.refresh(bill)

    return BillingResponse.model_validate(bill)


@router.get(
    "/subscriptions/{subscription_id}/bills",
    response_model=List[BillingResponse]
)
async def list_bills(
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    List all bills for a subscription.

    Returns bills ordered by billing_cycle_start descending.

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
        select(Billing)
        .where(Billing.subscription_id == subscription_id)
        .order_by(Billing.billing_cycle_start.desc())
    )
    bills = result.scalars().all()

    return [BillingResponse.model_validate(bill) for bill in bills]


@router.get(
    "/subscriptions/{subscription_id}/bills/{bill_id}",
    response_model=BillingResponse
)
async def get_bill(
    subscription_id: int,
    bill_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific bill.

    Raises:
    - 404 Not Found: If bill doesn't exist or doesn't belong to the subscription
    """
    bill = await db.scalar(
        select(Billing)
        .where(Billing.bill_id == bill_id)
        .where(Billing.subscription_id == subscription_id)
    )

    if not bill:
        raise HTTPException(
            status_code=404,
            detail=f"Bill {bill_id} not found for subscription {subscription_id}"
        )

    return BillingResponse.model_validate(bill)


@router.post(
    "/subscriptions/{subscription_id}/bills/{bill_id}/pay",
    response_model=BillingResponse
)
async def mark_bill_paid(
    subscription_id: int,
    bill_id: int,
    payment_data: BillingPaymentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a bill as paid.

    Sets paid=True and records the payment_date.

    Raises:
    - 404 Not Found: If bill doesn't exist or doesn't belong to the subscription
    """
    bill = await db.scalar(
        select(Billing)
        .where(Billing.bill_id == bill_id)
        .where(Billing.subscription_id == subscription_id)
    )

    if not bill:
        raise HTTPException(
            status_code=404,
            detail=f"Bill {bill_id} not found for subscription {subscription_id}"
        )

    bill.paid = True
    bill.payment_date = payment_data.payment_date if payment_data.payment_date else date.today()

    await db.flush()
    await db.refresh(bill)

    return BillingResponse.model_validate(bill)
