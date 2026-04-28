#!/usr/bin/env python3
"""
Intent Classifier Router Service

Sits between clients (chat UI, API) and the inference stack.  Classifies
each user turn via a fine-tuned BERT model (or fast-path when the client
supplies a predefined intent), assembles a reply from a pluggable
downstream provider, and maintains short-term conversation context in Redis.

Endpoints:
    POST /chat     – single turn: classify, reply, session update
    GET  /          – service metadata
    GET  /health    – liveness
    GET  /ready     – readiness (Redis + Postgres)
    GET  /config    – sanitised config diagnostic
    GET  /metrics   – Prometheus scrape

Usage:
    uvicorn src.router.router:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

from .models import ChatRequest, ChatResponse
from .classifier import BERTClassifier, Taxonomy, StubBackend, UserLookup
from .session import SessionManager, Archiver

# ─── Logging ──────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("router")

# ─── Configuration ────────────────────────────────────────────────────

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT_NUMBER", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "") or None
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_URL = os.getenv("REDIS_URL")
SESSION_TTL = 1800  # 30 minutes

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user_info:secret@pgvector:5432/userinfo",
)

VLLM_API_URL = os.getenv("VLLM_API_URL", "http://localhost:8080")
VLLM_API_TOKEN = os.getenv("VLLM_API_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_NAME", "finetuned-phayathai-bert")

_CONFIG_MOUNT = os.getenv("CONFIG_MOUNT_PATH", "")
_DEFAULT_INTENTS = str(Path(__file__).parent / "config" / "intents")
_DEFAULT_STUBS = str(Path(__file__).parent / "config" / "stubs.json")
INTENTS_FILE = os.getenv(
    "INTENTS_FILE",
    str(Path(_CONFIG_MOUNT) / "intents") if _CONFIG_MOUNT else _DEFAULT_INTENTS,
)
STUB_FILE = os.getenv(
    "STUB_FILE",
    str(Path(_CONFIG_MOUNT) / "stubs.json") if _CONFIG_MOUNT else _DEFAULT_STUBS,
)

AGENT_API_URL = os.getenv("AGENT_API_URL", "http://localhost:8080")
AGENT_INTENTS = {"MOBILE_USAGE_COMPARE_DATA_PLAN", "MOBILE_USAGE_CHECK_DATA_CURRENT"}

ARCHIVE_INTERVAL = int(os.getenv("ARCHIVE_INTERVAL", "120"))
ARCHIVE_TTL_THRESHOLD = int(os.getenv("ARCHIVE_TTL_THRESHOLD", "300"))
GOODBYE_INTENTS: set = set()

MAX_TURNS = int(os.getenv("MAX_TURNS", "5"))
BERT_CONFIDENCE_THRESHOLD = float(os.getenv("BERT_CONFIDENCE_THRESHOLD", "0.4"))

# ─── Prometheus Metrics ───────────────────────────────────────────────

intent_predictions_total = Counter(
    "intent_predictions_total",
    "Successful /chat resolutions by intent",
    ["intent"],
)
unknown_intent_total = Counter(
    "unknown_intent_total",
    "LLM returned label not in approved list",
)
system_error_total = Counter(
    "system_error_total",
    "LLM JSON parse errors or model call failures",
)


# ─── Context rewrite helper ──────────────────────────────────────────

def build_assistant_context(reply: str, backend_data: Optional[dict]) -> str:
    """Rewrite assistant text stored in Redis for BERT continuity."""
    if not backend_data or not isinstance(backend_data, dict):
        return reply

    bd_type = backend_data.get("type")
    if bd_type == "select":
        options = backend_data.get("options", [])
        titles = [o.get("title", "") for o in options if o.get("title")]
        if titles:
            return f"{reply} [option: {{{', '.join(titles)}}}]"
    elif bd_type == "action_link":
        return "[Self-Service UI Triggered]"

    return reply


# ─── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Intent Classifier Router starting")
    logger.info("=" * 60)

    # Redis
    if REDIS_URL:
        app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    else:
        app.state.redis = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True,
        )
    try:
        await app.state.redis.ping()
        logger.info("Redis connected (%s:%d/%d)", REDIS_HOST, REDIS_PORT, REDIS_DB)
    except Exception as exc:
        logger.error("Redis connection failed: %s", exc)

    # Postgres
    try:
        app.state.pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        logger.info("Postgres pool created")
    except Exception as exc:
        logger.error("Postgres pool creation failed: %s", exc)
        app.state.pg_pool = None

    # Components
    app.state.session_mgr = SessionManager(app.state.redis, max_turns=MAX_TURNS, ttl=SESSION_TTL)
    app.state.taxonomy = Taxonomy(INTENTS_FILE)
    app.state.stub = StubBackend(STUB_FILE)
    app.state.classifier = BERTClassifier(VLLM_API_URL, MODEL_NAME, VLLM_API_TOKEN)
    app.state.user_lookup = UserLookup(app.state.pg_pool) if app.state.pg_pool else None

    # Archiver
    if app.state.pg_pool:
        app.state.archiver = Archiver(
            app.state.pg_pool,
            app.state.session_mgr,
            interval=ARCHIVE_INTERVAL,
            ttl_threshold=ARCHIVE_TTL_THRESHOLD,
        )
        try:
            await app.state.archiver.ensure_table()
            app.state.archiver.start()
        except Exception as exc:
            logger.error("Archiver setup failed: %s", exc)
    else:
        app.state.archiver = None

    logger.info("Router ready")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Router shutting down")
    if app.state.archiver:
        await app.state.archiver.archive_all_remaining()
        await app.state.archiver.stop()
    if app.state.pg_pool:
        await app.state.pg_pool.close()
    await app.state.redis.aclose()
    logger.info("Router shutdown complete")


# ─── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Intent Classifier Router",
    description="NLU router: BERT classification → taxonomy guardrail → stub/agent reply",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return Response(
        content=json.dumps({
            "error": type(exc).__name__,
            "detail": "Internal server error",
            "path": str(request.url.path),
        }),
        status_code=500,
        media_type="application/json",
    )


# ── GET endpoints ─────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "intent-classifier-router",
        "status": "running",
        "endpoints": ["/health", "/ready", "/chat", "/config", "/metrics"],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "intent-classifier-router"}


@app.get("/ready")
async def ready(request: Request):
    checks: Dict[str, str] = {}

    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    try:
        pool = request.app.state.pg_pool
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["postgres"] = "ok"
        else:
            checks["postgres"] = "error: pool not initialised"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"

    checks["llm"] = f"configured ({MODEL_NAME})"

    ok = checks["redis"] == "ok" and checks["postgres"] == "ok"
    status_code = 200 if ok else 503
    return Response(
        content=json.dumps({"status": "ready" if ok else "not_ready", "checks": checks}),
        status_code=status_code,
        media_type="application/json",
    )


@app.get("/config")
async def config_endpoint():
    parsed = urlparse(DATABASE_URL)
    return {
        "redis": {
            "host": REDIS_HOST,
            "port": REDIS_PORT,
            "db": REDIS_DB,
            "password_configured": bool(REDIS_PASSWORD),
        },
        "postgres": {
            "host": parsed.hostname or "unknown",
            "port": parsed.port or 5432,
            "db": parsed.path.lstrip("/") if parsed.path else "unknown",
        },
        "llm": {
            "api_base": VLLM_API_URL,
            "model": MODEL_NAME,
            "token_configured": bool(VLLM_API_TOKEN),
        },
        "agent": {
            "url": AGENT_API_URL,
            "routed_intents": list(AGENT_INTENTS),
        },
    }


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── POST /chat ────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    start = time.time()
    sm: SessionManager = request.app.state.session_mgr
    taxonomy: Taxonomy = request.app.state.taxonomy
    stub: StubBackend = request.app.state.stub
    classifier: BERTClassifier = request.app.state.classifier
    archiver: Optional[Archiver] = request.app.state.archiver
    user_lookup: Optional[UserLookup] = request.app.state.user_lookup

    session_id = req.session_id or str(uuid.uuid4())
    intent = "UNKNOWN"
    reply = ""
    backend_data = None
    resolved_user: Optional[Dict[str, Any]] = None

    try:
        # ── User resolution ───────────────────────────────────────
        if user_lookup:
            resolved_user = await user_lookup.resolve(req.user_id)
            if resolved_user:
                logger.info(
                    "Resolved user '%s' → %s (%s)",
                    req.user_id, resolved_user["username"], resolved_user["display_name"],
                )
            else:
                logger.warning("User '%s' not found in userinfo database", req.user_id)

        # Username is the key for Redis/Postgres sessions.
        # Falls back to the raw user_id (email) if lookup fails.
        username = resolved_user["username"] if resolved_user else req.user_id

        # ── Intent resolution ─────────────────────────────────────
        if req.predefined_intent:
            if req.predefined_intent in taxonomy:
                intent = req.predefined_intent
            else:
                intent = "UNKNOWN"
                logger.warning(
                    "Unapproved predefined_intent '%s' → UNKNOWN (user=%s)",
                    req.predefined_intent, username,
                )
        else:
            try:
                window = await sm.get_window(username)
                bert_input = classifier.build_input(window, req.message)
                raw_intent, confidence = await classifier.classify(bert_input)
                logger.info(
                    "BERT classified '%s' (confidence=%.3f, user=%s)",
                    raw_intent, confidence, username,
                )

                if confidence < BERT_CONFIDENCE_THRESHOLD:
                    intent = "UNKNOWN"
                    unknown_intent_total.inc()
                    logger.warning(
                        "BERT confidence %.3f below threshold %.2f → UNKNOWN (user=%s)",
                        confidence, BERT_CONFIDENCE_THRESHOLD, username,
                    )
                elif raw_intent in taxonomy:
                    intent = raw_intent
                else:
                    intent = "UNKNOWN"
                    unknown_intent_total.inc()
                    logger.warning(
                        "BERT returned '%s' not in taxonomy → UNKNOWN (user=%s)",
                        raw_intent, username,
                    )
            except Exception as exc:
                intent = "SYSTEM_ERROR"
                system_error_total.inc()
                logger.error("BERT classification failed: %s", exc, exc_info=True)

        # ── Downstream reply ──────────────────────────────────────
        agent_user_id = resolved_user["email"] if resolved_user else req.user_id
        if intent in AGENT_INTENTS:
            reply, backend_data = await _call_agent(
                agent_user_id, req.message, session_id, intent, sm, username,
            )
        else:
            reply, backend_data = stub.get_response(intent)

        # ── Session update ────────────────────────────────────────
        assistant_ctx = build_assistant_context(reply, backend_data)
        new_length = await sm.append(
            username, req.user_id, session_id, req.message, assistant_ctx,
        )

        intent_predictions_total.labels(intent=intent).inc()

        # ── Archival trigger ──────────────────────────────────────
        if archiver:
            should_archive = new_length >= 10 or "ERROR" in intent
            delete_redis = intent in GOODBYE_INTENTS
            if should_archive or delete_redis:
                asyncio.create_task(
                    archiver.archive_session(username, delete_redis)
                )

        elapsed = (time.time() - start) * 1000
        logger.info(
            "POST /chat user=%s intent=%s elapsed=%.0fms",
            username, intent, elapsed,
        )
        return ChatResponse(
            session_id=session_id,
            reply=reply,
            intent=intent,
            user_info=resolved_user,
            backend_data=backend_data,
        )

    except Exception as exc:
        logger.error("POST /chat failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Agent routing helper ──────────────────────────────────────────────

async def _call_agent(
    user_id: str,
    message: str,
    session_id: str,
    intent: str,
    sm: SessionManager,
    username: str,
) -> tuple:
    """Route to the mobile plan recommendation agent and return (reply, backend_data)."""
    try:
        window = await sm.get_window(username)
        session_history = [
            {"role": m["role"], "content": m["content"]} for m in window
        ]

        async with httpx.AsyncClient(timeout=120, verify=False) as client:
            resp = await client.post(
                f"{AGENT_API_URL}/recommend",
                json={
                    "user_id": user_id,
                    "query": message,
                    "session_id": session_id,
                    "intent": intent,
                    "session_history": session_history,
                },
            )
            resp.raise_for_status()
            result = resp.json()

        return (
            result.get("reply", ""),
            {
                "type": "agent_recommendation",
                "tool_calls": result.get("tool_call_summary", []),
                "has_errors": result.get("has_errors", False),
            },
        )
    except Exception as exc:
        logger.error("Agent call failed: %s", exc, exc_info=True)
        return (
            "I'm having trouble reaching the recommendation service. Please try again.",
            {"type": "agent_error", "error": str(exc)},
        )


# ─── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("ROUTER_PORT", "8000"))
    host = os.getenv("ROUTER_HOST", "0.0.0.0")
    logger.info("Starting router on %s:%d", host, port)
    uvicorn.run("src.router.router:app", host=host, port=port, log_level="info")
