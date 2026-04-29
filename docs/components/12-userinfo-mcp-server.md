# 12 — UserInfo MCP Server

The UserInfo MCP Server is a simple implementation that demonstrates how to expose any REST API as an MCP server for LlamaStack agents. It acts as a thin proxy layer — each MCP tool maps directly to a UserInfo API endpoint, translating JSON-RPC tool calls into HTTP GET requests and returning the results as structured tool responses.

## What It Does

Bridges the UserInfo REST API (11) with the MCP protocol. When LlamaStack's agent calls an MCP tool (e.g., `get_user_info`), this server translates it into HTTP requests against the UserInfo API and returns structured results.

## Source Files

| File | Purpose |
|------|---------|
| `server.py` | FastAPI app with MCP JSON-RPC endpoint, health check, and root |
| `tools.py` | API helpers and the 5 tool handler functions |
| `tools_schema.py` | `TOOLS` dict (name → handler) and `TOOL_SCHEMAS` list (JSON schemas for `tools/list`) |

### MCP Tools

| Tool | Description | API Calls |
|------|-------------|-----------|
| `get_user_info` | Get user profile and subscriptions by username | `GET /api/v1/users?username={username}` → `GET /api/v1/users/{user_id}` |
| `get_user_subscriptions` | Get all subscriptions for a user | `GET /api/v1/users?username={username}` → `GET /api/v1/subscriptions?user_id={id}` |
| `get_current_plan` | Get the active plan for a mobile number | `GET /api/v1/subscriptions` → `GET /api/v1/subscriptions/{id}/plans` |
| `get_subscription_usage` | Get daily usage records for a mobile number | `GET /api/v1/subscriptions` → `GET /api/v1/subscriptions/{id}/usage` |
| `get_usage_insights` | Get usage insights for a mobile number | `GET /api/v1/subscriptions` → `GET /api/v1/subscriptions/{id}/insights` |

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/mcp` | MCP JSON-RPC endpoint (tool calls) |
| `GET` | `/health` | Health check |
| `GET` | `/` | Server info and available tools |

## Manifests

| File | Resource |
|------|----------|
| `deployment.yaml` | Deployment `userinfo-mcp-server` in `${NS_SERVICES}` |
| `service.yaml` | Service on port 8000 |
| `route.yaml` | Route with edge TLS |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `USERINFO_API_URL` | `http://userinfo-api.${NS_SERVICES}:8000` | UserInfo API base URL |
| `PORT` | `8000` | Listen port |

## Connections

- **11-userinfo-api** — All data fetched via HTTP
- **04-llamastack** — Registered as MCP toolgroup; called by agents during tool execution
- **01-rhoai-prereqs** — Listed in GenAI Studio ConfigMap
- **08-agent** — Default `MCP_TOOLGROUP` points to this server
