"""
Mobile Plan Recommendation Agent

Uses Llama Stack's Agents API (via REST) to orchestrate MCP tools
(user usage data) and RAG tools (pgvector plan search) for personalized
mobile plan recommendations.

The llama_stack_client SDK requires Python 3.10+ so we call the REST API
directly with httpx.  Llama Stack handles the agentic loop internally:
the LLM decides which tools to call, executes them, feeds results back,
and repeats until it produces a final answer.
"""

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import httpx

from .tools import AgentToolConfig, create_tool_config, validate_tool_configuration
from .prompts import (
    MOBILE_PLAN_AGENT_PROMPT,
    MOBILE_PLAN_AGENT_PROMPT_RAG_ONLY,
    MOBILE_USAGE_CHECK_PROMPT,
    MOBILE_USAGE_CHECK_PROMPT_RAG_ONLY,
    ERROR_USER_NOT_FOUND,
    ERROR_TOOLS_UNAVAILABLE,
)

logger = logging.getLogger(__name__)


class MobilePlanAgent:
    """
    Intelligent agent for personalized mobile plan recommendations.

    Uses Llama Stack Agents REST API with MCP tools and RAG to analyze
    user usage and recommend suitable mobile data plans.
    """

    def __init__(
        self,
        llama_stack_endpoint: Optional[str] = None,
        model_id: Optional[str] = None,
        mcp_toolgroup: Optional[str] = None,
        vector_db_id: Optional[str] = None,
    ):
        self.endpoint = llama_stack_endpoint or os.getenv(
            "LLAMA_STACK_ENDPOINT",
            "http://llamastack:5000",
        )
        self.model_id = model_id or os.getenv(
            "INFERENCE_MODEL", "vllm-inference/qwen25-7b-instruct"
        )
        self.tool_config = create_tool_config(
            mcp_toolgroup=mcp_toolgroup, vector_db_id=vector_db_id
        )
        validate_tool_configuration(self.tool_config, self.endpoint)

        self._agents: Dict[str, str] = {}

        logger.info(
            "Initialized MobilePlanAgent endpoint=%s model=%s",
            self.endpoint,
            self.model_id,
        )

    def _api(
        self,
        method: str,
        path: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Call Llama Stack REST API."""
        url = f"{self.endpoint}{path}"
        with httpx.Client(verify=False, timeout=120) as client:
            resp = getattr(client, method)(url, **kwargs)
            resp.raise_for_status()
            if stream:
                return resp
            return resp.json()

    def _refresh_mcp_status(self):
        """Re-check MCP tool availability (handles late-starting MCP servers)."""
        validate_tool_configuration(self.tool_config, self.endpoint)

    def _ensure_agent(self, intent: Optional[str] = None) -> str:
        """Create or retrieve a cached Llama Stack agent for the given intent."""
        agent_type = self._resolve_agent_type(intent)

        if agent_type in self._agents:
            return self._agents[agent_type]

        mcp_ok = getattr(self.tool_config, "mcp_available", True)

        if agent_type == "usage_check":
            prompt = MOBILE_USAGE_CHECK_PROMPT if mcp_ok else MOBILE_USAGE_CHECK_PROMPT_RAG_ONLY
            toolgroups = self._toolgroups_for_mcp_only() if mcp_ok else []
            max_iters = 5
        else:
            prompt = MOBILE_PLAN_AGENT_PROMPT if mcp_ok else MOBILE_PLAN_AGENT_PROMPT_RAG_ONLY
            toolgroups = self.tool_config.get_all_toolgroups()
            max_iters = 8

        logger.info(
            "Creating '%s' agent with toolgroups: %s (mcp_available=%s)",
            agent_type, toolgroups, mcp_ok,
        )
        body = {
            "agent_config": {
                "model": self.model_id,
                "instructions": prompt,
                "toolgroups": toolgroups,
                "sampling_params": {"max_tokens": 4096},
                "max_infer_iters": max_iters,
                "enable_session_persistence": False,
            }
        }
        resp = self._api("post", "/v1/agents", json=body)
        self._agents[agent_type] = resp["agent_id"]
        logger.info("Created Llama Stack agent '%s': %s", agent_type, resp["agent_id"])
        return resp["agent_id"]

    @staticmethod
    def _resolve_agent_type(intent: Optional[str]) -> str:
        if intent == "MOBILE_USAGE_CHECK_DATA_CURRENT":
            return "usage_check"
        return "compare_plan"

    def _toolgroups_for_mcp_only(self) -> List[Any]:
        """MCP toolgroup only — no RAG."""
        return [self.tool_config.mcp_toolgroup]

    def _create_session(self, agent_id: str, name: str) -> str:
        resp = self._api(
            "post",
            f"/v1/agents/{agent_id}/session",
            json={"session_name": name},
        )
        return resp["session_id"]

    def _create_turn_streaming(
        self,
        agent_id: str,
        session_id: str,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Send messages to the agent and collect the streamed response.

        Llama Stack streams the reply as Server-Sent Events (SSE). Each SSE
        line looks like ``data: {JSON}``.  The JSON contains an event with a
        ``payload`` whose ``event_type`` tells us what happened:

        - **step_progress** — a small chunk of text or a tool-call delta
          arrived (like receiving one word at a time).
        - **step_complete** — one full step finished.  Could be an LLM
          inference step (contains the model's text) or a tool execution
          step (contains tool results).
        - **turn_complete** — the whole agentic turn is done; the final
          answer is inside ``turn.output_message.content``.

        We accumulate text chunks as they arrive and capture every tool
        call so the caller knows which tools the agent used.
        """
        url = (
            f"{self.endpoint}/v1/agents/{agent_id}"
            f"/session/{session_id}/turn"
        )
        body = {"messages": messages, "stream": True}

        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        errors: List[str] = []

        with httpx.Client(verify=False, timeout=180) as client:
            with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    # SSE lines that carry data always start with "data: "
                    if not line.startswith("data: "):
                        continue
                    raw = line[len("data: "):]
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if "error" in event:
                        errors.append(event["error"].get("message", str(event["error"])))
                        continue

                    # Every event has: event -> payload -> event_type
                    payload = event.get("event", {}).get("payload", {})
                    etype = payload.get("event_type", "")

                    # --- Incremental progress: collect text/tool deltas ---
                    if etype == "step_progress":
                        delta = payload.get("text_delta", "")
                        if delta:
                            text_parts.append(delta)
                        tool_delta = payload.get("tool_call_delta", {})
                        if tool_delta and tool_delta.get("parse_status") == "succeeded":
                            tc = tool_delta.get("tool_call", {})
                            if tc:
                                tool_calls.append({
                                    "tool_name": tc.get("tool_name", "unknown"),
                                    "arguments": tc.get("arguments", {}),
                                })

                    # --- A full step finished (inference or tool execution) ---
                    elif etype == "step_complete":
                        step_detail = payload.get("step_details", {})
                        step_type = step_detail.get("step_type", "")

                        if step_type == "tool_execution":
                            for tr in step_detail.get("tool_responses", []):
                                tool_calls.append({
                                    "tool_name": tr.get("tool_name", "unknown"),
                                    "content": tr.get("content", ""),
                                })

                        if step_type == "inference":
                            mc = step_detail.get("model_response", {})
                            content = mc.get("content", "")
                            if isinstance(content, str) and content and not text_parts:
                                text_parts.append(content)

                    # --- The whole turn is done; grab the final answer ---
                    elif etype == "turn_complete":
                        turn = payload.get("turn", {})
                        output = turn.get("output_message", {})
                        content = output.get("content", "")
                        if isinstance(content, str) and content:
                            text_parts = [content]

        reply = "".join(text_parts).strip()
        return {
            "reply": reply,
            "tool_calls": tool_calls,
            "errors": errors,
            "has_errors": len(errors) > 0,
        }

    def get_recommendation(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str] = None,
        intent: Optional[str] = None,
        session_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Get personalized plan recommendation for a user.

        Args:
            session_history: Prior conversation turns from the NLU router
                (list of {"role": "user"|"assistant", "content": "..."}).
                Last 5 turns are kept to avoid context overflow.
            intent: Classified intent from the NLU router (informational).
        """
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:16]}"

        try:
            if not self._agents:
                self._refresh_mcp_status()

            agent_id = self._ensure_agent(intent=intent)
            ls_session = self._create_session(agent_id, session_id)

            parts = [f"User ID: {user_id}"]
            if intent:
                parts.append(f"Intent: {intent}")
            if session_history:
                parts.append("\nConversation so far:")
                for msg in session_history[-5:]:
                    role = msg["role"].capitalize()
                    parts.append(f"  {role}: {msg['content']}")
            parts.append(f"\nUser Query: {query}")

            user_message = "\n".join(parts)
            result = self._create_turn_streaming(
                agent_id, ls_session, [{"role": "user", "content": user_message}]
            )

            logger.info(
                "Recommendation completed: %d tool calls, errors=%s",
                len(result["tool_calls"]),
                result["has_errors"],
            )

            return {
                "session_id": session_id,
                "user_id": user_id,
                "query": query,
                "reply": result["reply"],
                "recommendations": [],
                "tool_calls": result["tool_calls"],
                "tool_call_summary": list({
                    tc["tool_name"] for tc in result["tool_calls"]
                }),
                "has_errors": result["has_errors"],
                "errors": result["errors"],
                "status": "success" if not result["has_errors"] else "partial",
            }
        except Exception as e:
            logger.error("Recommendation failed: %s", e, exc_info=True)
            return {
                "session_id": session_id,
                "user_id": user_id,
                "query": query,
                "reply": self._get_error_message(str(e)),
                "recommendations": [],
                "tool_calls": [],
                "tool_call_summary": [],
                "has_errors": True,
                "errors": [str(e)],
                "status": "error",
            }

    def get_simple_response(
        self,
        query: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a response without user-specific data."""
        if not session_id:
            session_id = f"simple_{uuid.uuid4().hex[:16]}"

        try:
            agent_id = self._ensure_agent()
            ls_session = self._create_session(agent_id, session_id)

            result = self._create_turn_streaming(
                agent_id, ls_session, [{"role": "user", "content": query}]
            )

            return {
                "session_id": session_id,
                "query": query,
                "reply": result["reply"],
                "status": "success",
            }
        except Exception as e:
            logger.error("Simple query failed: %s", e, exc_info=True)
            return {
                "session_id": session_id,
                "query": query,
                "reply": self._get_error_message(str(e)),
                "status": "error",
            }

    def health_check(self) -> Dict[str, Any]:
        try:
            resp = self._api("get", "/v1/models")
            models = resp.get("data", [])
            return {
                "status": "healthy",
                "llama_stack_endpoint": self.endpoint,
                "model": self.model_id,
                "available_models": len(models),
                "vector_db_id": self.tool_config.vector_db_id,
                "mcp_toolgroup": self.tool_config.mcp_toolgroup,
            }
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    def _get_error_message(error: str) -> str:
        if "user" in error.lower() and "not found" in error.lower():
            return ERROR_USER_NOT_FOUND.format(user_id="<unknown>")
        if "tool" in error.lower():
            return ERROR_TOOLS_UNAVAILABLE
        return (
            f"I encountered an error while processing your request: {error}\n\n"
            "Please try again or contact support if the issue persists."
        )


_agent_instance: Optional[MobilePlanAgent] = None


def get_agent_instance(
    llama_stack_endpoint: Optional[str] = None,
    model_id: Optional[str] = None,
    mcp_toolgroup: Optional[str] = None,
    vector_db_id: Optional[str] = None,
) -> MobilePlanAgent:
    """Get or create agent instance (singleton)."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = MobilePlanAgent(
            llama_stack_endpoint=llama_stack_endpoint,
            model_id=model_id,
            mcp_toolgroup=mcp_toolgroup,
            vector_db_id=vector_db_id,
        )
    return _agent_instance
