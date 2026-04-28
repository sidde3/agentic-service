"""
Users API Router

Endpoints:
- GET /users - List users with pagination and filters
- POST /users - Create a user
- GET /users/{user_id} - Get a user
- PUT /users/{user_id} - Update user details
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import User
from ..schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserWithSubscriptionsResponse,
    PaginatedUsersResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=PaginatedUsersResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    email: Optional[str] = Query(None, description="Filter by email"),
    username: Optional[str] = Query(None, description="Filter by username"),
    db: AsyncSession = Depends(get_db),
):
    """
    List users with pagination and optional filters.

    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - email: Filter by email (optional)
    - username: Filter by username (optional)
    """
    # Build query
    query = select(User)

    # Apply filters
    if email:
        query = query.where(User.email == email)
    if username:
        query = query.where(User.username == username)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    return PaginatedUsersResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[UserResponse.model_validate(user) for user in users],
    )


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user.

    Raises:
    - 409 Conflict: If username or email already exists
    """
    # Check if username exists
    existing_user = await db.scalar(
        select(User).where(User.username == user_data.username)
    )
    if existing_user:
        raise HTTPException(status_code=409, detail=f"Username '{user_data.username}' already exists")

    # Check if email exists
    existing_email = await db.scalar(
        select(User).where(User.email == user_data.email)
    )
    if existing_email:
        raise HTTPException(status_code=409, detail=f"Email '{user_data.email}' already exists")

    # Create user
    user = User(**user_data.model_dump())
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserWithSubscriptionsResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get user by ID with subscriptions.

    Raises:
    - 404 Not Found: If user doesn't exist
    """
    result = await db.execute(
        select(User)
        .where(User.user_id == user_id)
        .options(selectinload(User.subscriptions))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    return UserWithSubscriptionsResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update user details.

    Only provided fields will be updated.

    Raises:
    - 404 Not Found: If user doesn't exist
    - 409 Conflict: If username or email already taken by another user
    """
    # Get existing user
    user = await db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Update only provided fields
    update_data = user_data.model_dump(exclude_unset=True)

    # Check username uniqueness if being updated
    if "username" in update_data and update_data["username"] != user.username:
        existing = await db.scalar(
            select(User).where(User.username == update_data["username"])
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Username '{update_data['username']}' already exists",
            )

    # Check email uniqueness if being updated
    if "email" in update_data and update_data["email"] != user.email:
        existing = await db.scalar(
            select(User).where(User.email == update_data["email"])
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Email '{update_data['email']}' already exists",
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)

    return UserResponse.model_validate(user)
