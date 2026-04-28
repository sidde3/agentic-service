"""
Tool Configuration for Mobile Plan Recommendation Agent

Configures MCP tool groups and RAG tool group for the LlamaStack Agents API.
Tool groups are referenced by their identifiers registered in Llama Stack.
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_MCP_TOOLGROUP = "userinfo-mcp-server"
DEFAULT_RAG_TOOLGROUP = "builtin::rag"


class AgentToolConfig:
    """
    Configuration for agent tools.

    References Llama Stack tool groups by identifier. The Agents API
    resolves these to actual MCP endpoints and RAG runtimes.
    """

    def __init__(
        self,
        mcp_toolgroup: Optional[str] = None,
        vector_db_id: Optional[str] = None,
    ):
        self.mcp_toolgroup = mcp_toolgroup or os.getenv(
            "MCP_TOOLGROUP", DEFAULT_MCP_TOOLGROUP
        )
        self.vector_db_id = vector_db_id or os.getenv("VECTOR_DB_ID", "")
        if not self.vector_db_id:
            logger.warning(
                "VECTOR_DB_ID not set — RAG (knowledge_search) will not work. "
                "Run 01-create-vector-store.sh or set the env var."
            )

        logger.info(
            "Initialized tool config: mcp_toolgroup=%s, vector_db_id=%s",
            self.mcp_toolgroup,
            self.vector_db_id,
        )

    def get_rag_toolgroup(self) -> Dict[str, Any]:
        return {
            "name": DEFAULT_RAG_TOOLGROUP,
            "args": {"vector_db_ids": [self.vector_db_id]},
        }

    def get_all_toolgroups(self) -> List[Any]:
        """Return tool group references for the Llama Stack Agents API.

        If ``mcp_available`` is False (set during validation), only the
        RAG toolgroup is returned so the agent still works.
        """
        groups: List[Any] = []
        if getattr(self, "mcp_available", True):
            groups.append(self.mcp_toolgroup)
        else:
            logger.info("Excluding MCP toolgroup (unavailable)")
        groups.append(self.get_rag_toolgroup())
        return groups


def create_tool_config(
    mcp_toolgroup: Optional[str] = None,
    vector_db_id: Optional[str] = None,
) -> AgentToolConfig:
    return AgentToolConfig(mcp_toolgroup=mcp_toolgroup, vector_db_id=vector_db_id)


def validate_tool_configuration(
    config: AgentToolConfig,
    llama_stack_endpoint: Optional[str] = None,
) -> bool:
    """Validate tool groups exist on Llama Stack and check if MCP tools are resolvable.

    Sets ``config.mcp_available`` to indicate whether the MCP toolgroup
    has registered tools (i.e. the MCP server is reachable from Llama Stack).
    """
    config.mcp_available = True

    if not llama_stack_endpoint:
        logger.info("Skipping remote validation (no endpoint provided)")
        return True

    import httpx

    try:
        resp = httpx.get(
            f"{llama_stack_endpoint}/v1/toolgroups", verify=False, timeout=10
        )
        resp.raise_for_status()
        registered = {tg["identifier"] for tg in resp.json().get("data", [])}
        if config.mcp_toolgroup not in registered:
            logger.warning("MCP tool group '%s' not found on server", config.mcp_toolgroup)
            config.mcp_available = False
        if DEFAULT_RAG_TOOLGROUP not in registered:
            logger.warning("RAG tool group '%s' not found on server", DEFAULT_RAG_TOOLGROUP)

        # Check if MCP tools are actually resolvable
        if config.mcp_available:
            tools_resp = httpx.get(
                f"{llama_stack_endpoint}/v1/tools", verify=False, timeout=10
            )
            tools_resp.raise_for_status()
            mcp_tools = [
                t for t in tools_resp.json().get("data", [])
                if t.get("toolgroup_id") == config.mcp_toolgroup
            ]
            if not mcp_tools:
                logger.warning(
                    "MCP toolgroup '%s' exists but has no resolvable tools "
                    "(MCP server may be down); falling back to RAG-only",
                    config.mcp_toolgroup,
                )
                config.mcp_available = False
            else:
                logger.info(
                    "MCP toolgroup '%s' has %d tools",
                    config.mcp_toolgroup, len(mcp_tools),
                )

        logger.info("Tool configuration validated against %s", llama_stack_endpoint)
    except Exception as e:
        logger.warning("Could not validate tool groups remotely: %s", e)

    return True


def get_tool_descriptions() -> Dict[str, str]:
    return {
        "get_user_current_usage": "Retrieves current month's usage data including data used, voice minutes, SMS count, current plan, and overage charges",
        "get_usage_history": "Gets historical usage for the past 3-12 months to identify trends and patterns",
        "analyze_usage_patterns": "Provides AI-driven insights including average usage, trend analysis, usage category, and recommended data buffer",
        "get_overage_risk": "Calculates overage risk level with projected usage, days remaining, and actionable recommendations",
        "knowledge_search": "Searches the mobile data plans catalog using semantic search to find relevant plans based on user needs",
    }
