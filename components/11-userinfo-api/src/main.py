"""
FastAPI Application - Mobile Subscription Management API

Provides RESTful API endpoints for managing users, subscriptions, plans,
usage records, billing, and usage insights.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from .database import init_db, close_db
from .routers import users, subscriptions, plans, user_plans, usage, billing, insights


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown.
    """
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Mobile Subscription Management API",
    description="API for managing mobile users, subscriptions, plans, usage, and billing",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """
    Handle database errors.
    """
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Database error occurred",
            "error": str(exc),
        },
    )


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "mobile-subscription-api",
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "message": "Mobile Subscription Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


app.include_router(users.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(user_plans.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(insights.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
