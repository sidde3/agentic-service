"""
Async Database Connection for FastAPI

Uses SQLAlchemy 2.0 AsyncEngine with asyncpg driver.
"""

import os
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user_info:secret@pgvector:5432/userinfo"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    poolclass=NullPool if os.getenv("DISABLE_POOL", "false").lower() == "true" else None,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.

    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...

    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database connection pool.

    Call this on application startup.
    """
    # Test connection
    async with engine.begin() as conn:
        # Connection test - just execute a simple query
        await conn.execute(text("SELECT 1"))

    print(f"✓ Database connection established: {DATABASE_URL.split('@')[1]}")


async def close_db() -> None:
    """
    Close database connection pool.

    Call this on application shutdown.
    """
    await engine.dispose()
    print("✓ Database connection pool closed")
