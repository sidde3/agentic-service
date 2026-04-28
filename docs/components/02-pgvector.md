# 02 — pgvector (PostgreSQL)

Single-node PostgreSQL instance with the `pgvector` extension, hosting all application databases.

## What It Does

Deploys a PostgreSQL StatefulSet with a 10Gi PVC. Post-deploy Kubernetes Jobs initialize databases, create roles, enable the `vector` extension, and seed sample data.

## Databases

| Database | Role | Purpose |
|----------|------|---------|
| `pgvector` (default) | `appuser` | Vector store for RAG. `vector` extension enabled. |
| `userinfo` | `user_info` | User profiles, subscriptions, plans, usage, billing, insights, chat sessions. |
| `llamastack` | `llamastack` | LlamaStack internal state (KV store, SQL store). |

## Source Files

### `post-deploy/populate_postgres_userdata.py`
Python script that creates the `userinfo` schema and seeds it with sample data:
- **`create_tables()`** — DDL for 8 tables: `users`, `subscriptions`, `plans`, `user_plans`, `usage_records`, `billing`, `usage_insights`, `chat_sessions` (simplified: `username` PK + `history` JSONB)
- **`seed_plans()`** — Inserts standard mobile plans (Basic, Standard, Premium, Unlimited)
- **`seed_from_json()`** — Parses `sample_usage.json` and populates users, subscriptions, usage records, billing, and insights
- **`verify()`** — Counts rows in each table

### `post-deploy/01-db-init-job.yaml`
Kubernetes Job `db-init` with embedded SQL ConfigMap:
- Creates databases `userinfo` and `llamastack`
- Creates roles with passwords from env vars
- Grants privileges
- Enables `vector` extension on the default DB

### `post-deploy/02-db-seed-job.yaml`
Kubernetes Job `db-seed-userinfo`:
- Runs `populate_postgres_userdata.py` in a `python:3.12-slim` container
- Mounts the script and `sample_usage.json` via ConfigMaps

### `data/sample_usage.json`
Rich JSON profiles with user details, plans, usage history, and billing data.

## Manifests

| File | Resource |
|------|----------|
| `manifests/namespace.yaml` | Namespace `${NS_PGVECTOR}` |
| `manifests/statefulset.yaml` | Secret, headless Service, StatefulSet (image: `pgvector/pgvector:pg15`) |

## Configuration

| Variable | Source | Purpose |
|----------|--------|---------|
| `PGVECTOR_USER` / `PGVECTOR_PASSWORD` | env.properties | Superuser credentials |
| `PG_USERINFO_USER` / `PG_USERINFO_PASSWORD` | env.properties | `userinfo` DB role |
| `PG_LLAMASTACK_USER` / `PG_LLAMASTACK_PASSWORD` | env.properties | `llamastack` DB role |

## Connections

- **04-llamastack** connects to `llamastack` DB for state and `pgvector` DB for vectors
- **06-usage-mcp-server** reads from `userinfo` DB
- **09-router** reads users and archives chat sessions to `userinfo` DB
- **11-userinfo-api** provides REST access to `userinfo` DB
