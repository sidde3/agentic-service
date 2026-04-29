#!/usr/bin/env python3
"""
User Info MCP Server

Exposes user-subscription data as MCP tools via JSON-RPC 2.0.
Tool definitions and handlers live in tools.py.

Protocol:  JSON-RPC 2.0  (POST /mcp)
Health:    GET /health
"""

import logging
import os
from typing import Optional, Union

import uvicorn
from fastapi import FastAPI, Response
from pydantic import BaseModel

from tools import USERINFO_API_URL
from tools_schema import TOOLS, TOOL_SCHEMAS

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="User Info MCP Server", version="1.0.0")


#Needed for Openshift GenAI Studio
class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict] = None
    id: Optional[Union[int, str]] = None


def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

@app.post("/mcp")
async def mcp_endpoint(request: JSONRPCRequest):
    logger.info("MCP %s (id=%s)", request.method, request.id)

    if request.method == "initialize":
        proto = (request.params or {}).get("protocolVersion", "2024-11-05")
        return _ok(request.id, {
            "protocolVersion": proto,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "userinfo-mcp-server", "version": "1.0.0"},
        })

    if request.method == "ping":
        return _ok(request.id, {})

    if request.method == "notifications/initialized":
        return Response(status_code=204)

    if request.method == "tools/list":
        return _ok(request.id, {"tools": TOOL_SCHEMAS})

    if request.method == "tools/call":
        params = request.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        handler = TOOLS.get(tool_name)
        if not handler:
            return _err(request.id, -32601, f"Unknown tool: {tool_name}")

        try:
            result_text = await handler(arguments)
            return _ok(request.id, {"content": [{"type": "text", "text": result_text}]})
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e, exc_info=True)
            return _err(request.id, -32603, f"Tool error: {e}")

    return _err(request.id, -32601, f"Method not found: {request.method}")


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"name": "User Info MCP Server", "tools": list(TOOLS.keys()), "api_url": USERINFO_API_URL}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
