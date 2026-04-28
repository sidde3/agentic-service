# 06 — Usage MCP Server

FastAPI-based MCP (Model Context Protocol) server that queries mobile usage data directly from the `userinfo` PostgreSQL database.

## What It Does

Provides MCP tools over JSON-RPC at `POST /mcp`. Each tool executes SQL against the `userinfo` database using an asyncpg connection pool. This server can be used standalone via LlamaStack or GenAI Studio.

## Source: `src/server.py`

### Key Functions

- **`get_user_current_usage`** — Returns current billing period usage (data consumed, remaining, percentage)
- **`get_usage_history`** — Historical usage records with optional date range filter
- **`analyze_usage_patterns`** — Statistical analysis of usage patterns (averages, trends, peaks)
- **`get_overage_risk`** — Assesses risk of exceeding data plan based on current trajectory
- **`_resolve_user_id(identifier)`** — Resolves user by email, username, or external ID

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/mcp` | MCP JSON-RPC endpoint (tool calls) |
| `GET` | `/healthz` | Health check (includes DB ping) |

## Manifests

| File | Resource |
|------|----------|
| `manifests/deployment.yaml` | Deployment `usage-mcp-server-v2`, Service, Route |

## Post-Deploy

`01-register-mcp-toolgroup.sh` — Registers this MCP server as a toolgroup in LlamaStack via `POST ${LLAMASTACK_URL}/v1/toolgroups`.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_HOST` | `pgvector.${NS_PGVECTOR}.svc.cluster.local` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `userinfo` | Database name |
| `DB_USER` | `user_info` | Database role |
| `DB_PASSWORD` | — | Database password |
| `MCP_SERVER_HOST` | `0.0.0.0` | Listen host |
| `MCP_SERVER_PORT` | `8000` | Listen port |

## Connections

- **02-pgvector** — Reads from `userinfo` database
- **04-llamastack** — Registered as a toolgroup; callable by agents
- **00-rhoai-prereqs** — Listed in GenAI Studio ConfigMap
