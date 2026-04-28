#!/usr/bin/env python3
"""
Hello World MCP Server

A simple MCP server for testing GenAI Studio integration.
Uses JSON-RPC protocol over HTTP.
"""

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
import uvicorn
import os
import traceback

app = FastAPI(title="Hello World MCP Server")


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict | None = None
    id: int | str | None = None


@app.post("/mcp")
async def mcp_endpoint(request: JSONRPCRequest):
    """MCP JSON-RPC endpoint."""

    print(f"Received request: method={request.method}, id={request.id}, params={request.params}")

    try:
        if request.method == "initialize":
            params = request.params or {}
            client_protocol = params.get("protocolVersion", "2024-11-05")

            response_data = {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "protocolVersion": client_protocol,
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "hello-world-mcp",
                        "version": "1.0.0"
                    }
                }
            }
            print(f"Initialize response: {response_data}")
            return response_data

        elif request.method == "ping":
            response_data = {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {}
            }
            print(f"Ping response: {response_data}")
            return response_data

        elif request.method == "notifications/initialized":
            # Notifications don't need a JSON-RPC response - return 204 No Content
            print("Received initialized notification - no response needed")
            return Response(status_code=204)

        elif request.method == "tools/list":
            response_data = {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "tools": [
                        {
                            "name": "greet",
                            "description": "Generate a friendly greeting",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "The name of the person to greet"
                                    }
                                },
                                "required": ["name"]
                            }
                        },
                        {
                            "name": "echo",
                            "description": "Echo back the provided message",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "message": {
                                        "type": "string",
                                        "description": "The message to echo back"
                                    }
                                },
                                "required": ["message"]
                            }
                        },
                        {
                            "name": "get_server_info",
                            "description": "Get information about the MCP server",
                            "inputSchema": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    ]
                }
            }
            return response_data

        elif request.method == "tools/call":
            params = request.params or {}
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "greet":
                person_name = arguments.get("name", "World")
                result = f"Hello, {person_name}! Welcome to the MCP Server demo!"

            elif tool_name == "echo":
                message = arguments.get("message", "")
                result = f"Echo: {message}"

            elif tool_name == "get_server_info":
                result = str({
                    "server_name": "Hello World MCP Server",
                    "version": "1.0.0",
                    "description": "A simple MCP server for testing GenAI Studio integration",
                    "available_tools": ["greet", "echo", "get_server_info"]
                })

            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }

            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                }
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {request.method}"
                }
            }

    except Exception as e:
        print(f"Error handling request: {e}")
        traceback.print_exc()
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }


@app.get("/healthz")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "server": "hello-world-mcp"}


if __name__ == "__main__":
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SERVER_PORT", "8000"))

    print(f"Starting Hello World MCP Server (JSON-RPC)")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"MCP endpoint: http://{host}:{port}/mcp")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port, log_level="info")
