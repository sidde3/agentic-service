"""
Plans API Router

Endpoints:
- GET /plans - List all plans with pagination
- POST /plans - Create a new plan
- GET /plans/{plan_id} - Get a plan
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Plan
from ..schemas import (
    PlanCreate,
    PlanResponse,
    PaginatedPlansResponse,
)

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get("", response_model=PaginatedPlansResponse)
async def list_plans(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all plans with pagination.

    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    query = select(Plan)

    count_query = select(func.count()).select_from(Plan)
    total = await db.scalar(count_query)

    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    plans = result.scalars().all()

    return PaginatedPlansResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[PlanResponse.model_validate(plan) for plan in plans],
    )


@router.post("", response_model=PlanResponse, status_code=201)
async def create_plan(
    plan_data: PlanCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new plan.

    Raises:
    - 409 Conflict: If plan_name already exists
    """
    existing = await db.scalar(
        select(Plan).where(Plan.plan_name == plan_data.plan_name)
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Plan '{plan_data.plan_name}' already exists"
        )

    plan = Plan(**plan_data.model_dump())
    db.add(plan)
    await db.flush()
    await db.refresh(plan)

    return PlanResponse.model_validate(plan)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get plan by ID.

    Raises:
    - 404 Not Found: If plan doesn't exist
    """
    plan = await db.scalar(
        select(Plan).where(Plan.plan_id == plan_id)
    )

    if not plan:
        raise HTTPException(
            status_code=404,
            detail=f"Plan {plan_id} not found"
        )

    return PlanResponse.model_validate(plan)
