# 07 — HelloWorld MCP Server

Minimal MCP server for testing MCP integration in GenAI Studio.

## What It Does

A simple FastAPI MCP server with three basic tools, useful for verifying that the MCP protocol pipeline (GenAI Studio → LlamaStack → MCP server) works correctly.

## Source: `src/server.py`

### Tools

| Tool | Description |
|------|-------------|
| `greet` | Returns a greeting message for a given name |
| `echo` | Echoes back the input text |
| `get_server_info` | Returns server metadata (name, version, uptime) |

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/mcp` | MCP JSON-RPC endpoint |
| `GET` | `/healthz` | Health check |

## Manifests

| File | Resource |
|------|----------|
| `manifests/deployment.yaml` | Deployment `helloworld-mcp-server`, Service, Route |

## Configuration

No database or external dependencies. Listens on port 8000.

## Connections

- **00-rhoai-prereqs** — Listed in GenAI Studio ConfigMap for playground testing
