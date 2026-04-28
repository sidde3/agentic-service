# 11 — UserInfo API

RESTful CRUD API over the `userinfo` database, built with FastAPI and SQLAlchemy (async).

## What It Does

Provides a complete REST API for querying and managing user information stored in the `userinfo` PostgreSQL database. This API is consumed by the UserInfo MCP server (12) to serve data to LlamaStack agents.

## Source Files

### `src/main.py`
FastAPI application factory. Mounts all routers under `/api/v1` prefix. Includes CORS middleware and health endpoint.

### `src/database.py`
SQLAlchemy async engine and session factory. Reads `DATABASE_URL` from environment.

### `src/models.py`
SQLAlchemy ORM models for all 8 tables: `users`, `subscriptions`, `plans`, `user_plans`, `usage_records`, `billing`, `usage_insights`, `chat_sessions`.

### `src/schemas.py`
Pydantic schemas for request/response serialization.

### `src/routers/`
One router module per resource:

| Module | Prefix | Key Endpoints |
|--------|--------|---------------|
| `users.py` | `/users` | GET list, GET by ID, GET by email |
| `subscriptions.py` | `/subscriptions` | GET list, GET by ID, GET by user |
| `plans.py` | `/plans` | GET list, GET by ID |
| `user_plans.py` | `/user-plans` | GET list, GET by user |
| `usage.py` | `/usage` | GET records, GET aggregates, GET by subscription |
| `billing.py` | `/billing` | GET records, GET by subscription |
| `insights.py` | `/insights` | GET list, GET by user |

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/users` | List users |
| `GET` | `/api/v1/users/{id}` | Get user by ID |
| `GET` | `/api/v1/subscriptions/{id}/usage` | Usage for a subscription |
| ... | `/api/v1/*` | Full CRUD across all resources |

## Manifests

| File | Resource |
|------|----------|
| `deployment.yaml` | Deployment `userinfo-api` in `${NS_SERVICES}` |
| `service.yaml` | Service on port 8000 |
| `route.yaml` | Route with edge TLS |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | — | Async PostgreSQL connection string (set via envsubst in manifest) |
| `PORT` | `8000` | Listen port |
| `SQL_ECHO` | `false` | Enable SQL query logging |

## Connections

- **02-pgvector** — Reads/writes `userinfo` database
- **12-userinfo-mcp-server** — Primary consumer (HTTP calls to `/api/v1/*`)
