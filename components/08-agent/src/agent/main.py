#!/usr/bin/env python3
"""
FastAPI Service for Mobile Plan Recommendation Agent

Provides REST API endpoints for the LlamaStack-based agent.

Endpoints:
- POST /recommend - Get personalized plan recommendations
- POST /chat     - Simple query without user context
- GET  /health   - Health check

Usage:
    uvicorn src.agent.main:app --host 0.0.0.0 --port 8080
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from src.agent.mobile_plan_agent import MobilePlanAgent, get_agent_instance

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ── Request / Response models ────────────────────────────────────────

class SessionMessage(BaseModel):
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class RecommendationRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    query: str = Field(..., description="User's question or request")
    session_id: Optional[str] = Field(None, description="Session ID (optional)")
    intent: Optional[str] = Field(None, description="Classified intent from NLU router")
    session_history: Optional[List[SessionMessage]] = Field(
        None, description="Prior conversation turns from the NLU router"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_heavy_1",
                "query": "How are these packages different? I'd like to know which one is more worth it",
                "intent": "MOBILE_USAGE_COMPARE_DATA_PLAN",
                "session_history": [
                    {"role": "user", "content": "I'd like to ask about monthly data packages."},
                    {"role": "assistant", "content": "Sure! What would you like to know?"},
                ],
            }
        }


class ChatRequest(BaseModel):
    query: str = Field(..., description="User's question")
    session_id: Optional[str] = Field(None, description="Session ID (optional)")

    class Config:
        json_schema_extra = {"example": {"query": "What unlimited plans do you offer?"}}


class RecommendationResponse(BaseModel):
    session_id: str
    user_id: str
    query: str
    reply: str
    recommendations: list
    tool_calls: list
    tool_call_summary: list
    has_errors: bool
    errors: list
    status: str


class ChatResponse(BaseModel):
    session_id: str
    query: str
    reply: str
    status: str


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Mobile Plan Agent API starting")
    logger.info("=" * 60)

    try:
        agent = get_agent_instance()
        health = agent.health_check()
        logger.info("Agent health: %s", health)
    except Exception as e:
        logger.warning("Agent init failed (will retry on first request): %s", e)

    logger.info("Agent API ready")
    logger.info("=" * 60)
    yield
    logger.info("Agent API shutting down")


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Mobile Plan Recommendation Agent API",
    description="Intelligent agent for personalized mobile data plan recommendations using Llama Stack",
    version="2.0.0",
    lifespan=lifespan,
)


@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_plan(request: RecommendationRequest):
    """Get personalized mobile plan recommendations based on user usage."""
    start = time.time()
    logger.info("POST /recommend user_id=%s", request.user_id)

    try:
        agent = get_agent_instance()
        history = (
            [{"role": m.role, "content": m.content} for m in request.session_history]
            if request.session_history
            else None
        )
        result = agent.get_recommendation(
            user_id=request.user_id,
            query=request.query,
            session_id=request.session_id,
            intent=request.intent,
            session_history=history,
        )
        logger.info(
            "POST /recommend completed in %.1fs tools=%s",
            time.time() - start,
            result.get("tool_call_summary", []),
        )
        return result
    except Exception as e:
        logger.error("POST /recommend failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """General query without user-specific context."""
    start = time.time()
    logger.info("POST /chat query=%s", request.query[:60])

    try:
        agent = get_agent_instance()
        result = agent.get_simple_response(
            query=request.query, session_id=request.session_id
        )
        logger.info("POST /chat completed in %.1fs", time.time() - start)
        return result
    except Exception as e:
        logger.error("POST /chat failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend/pretty", response_class=PlainTextResponse)
async def recommend_plan_pretty(request: RecommendationRequest):
    """Get personalized recommendations with human-readable plain-text output."""
    start = time.time()
    logger.info("POST /recommend/pretty user_id=%s", request.user_id)

    try:
        agent = get_agent_instance()
        history = (
            [{"role": m.role, "content": m.content} for m in request.session_history]
            if request.session_history
            else None
        )
        result = agent.get_recommendation(
            user_id=request.user_id,
            query=request.query,
            session_id=request.session_id,
            intent=request.intent,
            session_history=history,
        )
        elapsed = time.time() - start
        logger.info(
            "POST /recommend/pretty completed in %.1fs tools=%s",
            elapsed,
            result.get("tool_call_summary", []),
        )

        tools = result.get("tool_call_summary", [])
        lines = [
            f"Status: {result['status']}",
            f"Tools:  {tools}",
            f"VectorDB called: {'knowledge_search' in tools}",
            f"Time:   {elapsed:.1f}s",
            "",
            "─" * 60,
            "",
            result.get("reply", "(no reply)"),
        ]

        if result.get("has_errors") and result.get("errors"):
            lines.append("")
            lines.append("─" * 60)
            lines.append("ERRORS:")
            for err in result["errors"]:
                lines.append(f"  - {err}")

        return "\n".join(lines)
    except Exception as e:
        logger.error("POST /recommend/pretty failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check."""
    try:
        agent = get_agent_instance()
        status = agent.health_check()
        if status["status"] == "healthy":
            return status
        raise HTTPException(status_code=503, detail=status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503, detail={"status": "unhealthy", "error": str(e)}
        )


@app.get("/")
async def root():
    return {
        "service": "Mobile Plan Recommendation Agent",
        "version": "2.0.0",
        "endpoints": {
            "recommend": "POST /recommend - Personalized plan recommendations (JSON)",
            "recommend_pretty": "POST /recommend/pretty - Personalized recommendations (plain text)",
            "chat": "POST /chat - General plan questions",
            "health": "GET /health - Health check",
        },
        "status": "ready",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AGENT_PORT", "8080"))
    host = os.getenv("AGENT_HOST", "0.0.0.0")
    logger.info("Starting agent API on %s:%d", host, port)
    uvicorn.run("src.agent.main:app", host=host, port=port, log_level="info")
