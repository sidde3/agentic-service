#!/usr/bin/env python3
"""
Agent — FastAPI based implementation for LLamastack based agentic execution.

Flow:  POST /recommend  →  get_recommendation()  →  _get_or_create_agent()
                                                  →  _run_turn()
                                                  →  return JSON result

Endpoints:
    POST /recommend  — called by the router for plan recommendations
    GET  /health     — liveness check (verifies Llama Stack connectivity)
"""

import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.prompts import (
    MOBILE_PLAN_AGENT_PROMPT,
    MOBILE_USAGE_CHECK_PROMPT,
    ERROR_USER_NOT_FOUND,
    ERROR_TOOLS_UNAVAILABLE,
)
from src.agent import reranker

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


LLAMA_STACK = os.getenv("LLAMA_STACK_ENDPOINT", "http://llamastack:5000")
MODEL = os.getenv("INFERENCE_MODEL", "vllm-inference/qwen25-7b-instruct")
MCP_TOOLGROUP = os.getenv("MCP_TOOLGROUP", "userinfo-mcp-server")
VECTOR_DB_ID = os.getenv("VECTOR_DB_ID", "")

_agents: Dict[str, str] = {}

def _api(method: str, path: str, **kwargs) -> dict:
    """Call Llama Stack REST API and return parsed JSON."""
    with httpx.Client(base_url=LLAMA_STACK, verify=False, timeout=120) as c:
        resp = getattr(c, method)(path, **kwargs)
        resp.raise_for_status()
        return resp.json()


def _search_and_rerank(query: str) -> Optional[str]:
    """Search the vector store and rerank results.

    Returns formatted context string to prepend to the user message,
    or None if reranking is disabled or search fails.
    """
    if not reranker.is_enabled() or not VECTOR_DB_ID:
        return None

    try:
        resp = _api("post", f"/v1/vector_stores/{VECTOR_DB_ID}/search",
                     json={"query": query, "top_k": reranker.RERANK_TOP_K})

        documents = []
        for r in resp.get("data", []):
            content = r.get("content", "")
            if isinstance(content, list) and content:
                content = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
            if content:
                documents.append(str(content))

        if not documents:
            return None

        logger.info("[RERANK] Vector search returned %d candidates", len(documents))
        reranked = reranker.rerank(query, documents)

        parts = []
        for i, doc in enumerate(reranked, 1):
            parts.append(f"Plan {i} (relevance: {doc['score']:.3f}):\n{doc['text']}")
        return "\n\n".join(parts)

    except Exception as e:
        logger.warning("[RERANK] Search failed: %s", e)
        return None

def _get_or_create_agent(intent: str) -> str:
    """Create (or reuse) a Llama Stack agent for this intent.
    usage_check  →  MCP tools only      (check current data usage)
    plan compare →  MCP + RAG tools     (compare/recommend plans)
    """
    is_usage_check = (intent == "MOBILE_USAGE_CHECK_DATA_CURRENT")
    key = "usage" if is_usage_check else "plan"

    # Check if the agent already exists in the cache
    if key in _agents:
        return _agents[key]

    toolgroups: List[Any] = [MCP_TOOLGROUP]
    if not is_usage_check and VECTOR_DB_ID:
        toolgroups.append({
            "name": "builtin::rag",
            "args": {"vector_db_ids": [VECTOR_DB_ID]},
        })

    resp = _api("post", "/v1/agents", json={"agent_config": {
        "model": MODEL,
        "instructions": MOBILE_USAGE_CHECK_PROMPT if is_usage_check else MOBILE_PLAN_AGENT_PROMPT,
        "toolgroups": toolgroups,
        "sampling_params": {"max_tokens": 4096},
        "max_infer_iters": 5 if is_usage_check else 8,
        "enable_session_persistence": False,
    }})

    _agents[key] = resp["agent_id"]
    logger.info("Created '%s' agent → %s  toolgroups=%s", key, resp["agent_id"], toolgroups)
    return resp["agent_id"]

def _run_turn(agent_id: str, session_id: str, messages: list) -> dict:
    """Stream a turn from LlamaStack and return the final reply + tool names."""
    reply = ""
    tool_names = []

    with httpx.Client(base_url=LLAMA_STACK, verify=False, timeout=300) as c:
        with c.stream(
            "POST",
            f"/v1/agents/{agent_id}/session/{session_id}/turn",
            json={"messages": messages, "stream": True},
        ) as stream:
            stream.raise_for_status()
            for line in stream.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                payload = event.get("event", {}).get("payload", {})

                if payload.get("event_type") == "turn_complete":
                    turn = payload.get("turn", {})
                    reply = turn.get("output_message", {}).get("content", "")
                    for step in turn.get("steps", []):
                        if step.get("step_type") == "tool_execution":
                            for tr in step.get("tool_responses", []):
                                tool_names.append(tr.get("tool_name", "unknown"))

    logger.info("[AGENT] Turn done — tools=%s  reply=%d chars", tool_names or "none", len(reply))
    return {"reply": reply, "tool_names": list(set(tool_names)), "errors": []}

def get_recommendation(
    user_id: str,
    query: str,
    session_id: str = None,
    intent: str = None,
) -> dict:
    """
    Steps:
        1. Create (or reuse) a Llama Stack agent for this intent
        2. Open a new session
        3. Build the user message (user ID + query)
        4. Run the agent turn — LLM calls tools, gets results, responds
        5. Return structured result
    """
    session_id = session_id or f"s_{uuid.uuid4().hex[:12]}"
    intent = intent or "MOBILE_USAGE_COMPARE_DATA_PLAN"
    logger.info("[AGENT] user=%s  intent=%s", user_id, intent)

    try:
        # Step 1 — get or create agent
        agent_id = _get_or_create_agent(intent)

        # Step 2 — open a new session
        sid = _api("post", f"/v1/agents/{agent_id}/session",
                    json={"session_name": session_id})["session_id"]

        # Step 3 — build user message (with optional reranked context)
        parts = [f"User ID: {user_id}", f"Intent: {intent}"]

        if reranker.is_enabled() and intent != "MOBILE_USAGE_CHECK_DATA_CURRENT":
            context = _search_and_rerank(query)
            if context:
                parts.append(f"\nRelevant plans (reranked):\n{context}")

        parts.append(f"\nUser Query: {query}")

        # Step 4 — run agent turn
        result = _run_turn(agent_id, sid, [{"role": "user", "content": "\n".join(parts)}])

        # Step 5 — return result
        return {
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "reply": result["reply"],
            "recommendations": [],
            "tool_calls": [],
            "tool_call_summary": result["tool_names"],
            "has_errors": bool(result["errors"]),
            "errors": result["errors"],
            "status": "success" if not result["errors"] else "partial",
        }

    except Exception as e:
        logger.error("Recommendation failed: %s", e, exc_info=True)
        err = str(e).lower()
        if "not found" in err and "user" in err:
            msg = ERROR_USER_NOT_FOUND.format(user_id=user_id)
        elif "tool" in err:
            msg = ERROR_TOOLS_UNAVAILABLE
        else:
            msg = f"Error: {e}. Please try again."

        return {
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "reply": msg,
            "recommendations": [],
            "tool_calls": [],
            "tool_call_summary": [],
            "has_errors": True,
            "errors": [str(e)],
            "status": "error",
        }

class RequestModel(BaseModel):
    user_id: str = Field(..., description="User email")
    query: str = Field(..., description="User question")
    session_id: Optional[str] = None
    intent: Optional[str] = None

class ResponseModel(BaseModel):
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

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Agent API starting")
    logger.info("[RERANK] %s", "ENABLED" if reranker.is_enabled() else "DISABLED")
    try:
        models = _api("get", "/v1/models")
        logger.info("Llama Stack OK — %d models", len(models.get("data", [])))
    except Exception as e:
        logger.warning("Llama Stack not ready yet: %s", e)
    yield
    logger.info("Agent API stopping")


app = FastAPI(title="Mobile Plan Agent", version="2.0.0", lifespan=lifespan)


@app.post("/recommend", response_model=ResponseModel)
async def recommend_endpoint(req: RequestModel):
    """Personalised mobile plan recommendations — called by the router."""
    start = time.time()
    result = get_recommendation(req.user_id, req.query, req.session_id, req.intent)
    logger.info("POST /recommend  %.1fs  tools=%s", time.time() - start, result["tool_call_summary"])
    return result


@app.get("/health")
async def health():
    """Liveness check — verifies Llama Stack is reachable."""
    try:
        models = _api("get", "/v1/models")
        return {"status": "healthy", "models": len(models.get("data", []))}
    except Exception as e:
        raise HTTPException(503, {"status": "unhealthy", "error": str(e)})


@app.get("/")
async def root():
    return {"service": "Mobile Plan Agent", "endpoints": ["POST /recommend", "GET /health"]}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("AGENT_PORT", "8080"))
    uvicorn.run("src.agent.server:app", host="0.0.0.0", port=port, log_level="info")