# 02 — pgvector (PostgreSQL)

Single-node PostgreSQL instance with the `pgvector` extension, hosting all application databases.

## What It Does

Deploys a PostgreSQL StatefulSet with a 10Gi PVC. Post-deploy Kubernetes Job **`db-init`** does all database setup in one run: extension, databases, roles, **userinfo** tables, and sample data with **at least 10 rows per table** (embedded SQL in the Job’s ConfigMap).

## Databases

| Database | Role | Purpose |
|----------|------|---------|
| `pgvector` (default) | `appuser` | Vector store for RAG. `vector` extension enabled. |
| `userinfo` | `user_info` | User profiles, subscriptions, plans, usage, billing, insights, chat sessions. |
| `llamastack` | `llamastack` | LlamaStack internal state (KV store, SQL store). |

## Source Files

### `post-deploy/01-db-init-job.yaml`
Kubernetes Job `db-init` with ConfigMap `db-init-sql`:
- **`init.sql`** (admin): creates databases `userinfo` and `llamastack`, roles, grants, owner; enables `vector` on the default DB.
- **`userinfo_seed.sql`** (same Job, second `psql` as `PG_USERINFO_USER`): eight tables, `TRUNCATE … CASCADE`, then **10 rows** seeded per table (including `jessica.thompson@example.com` and nine other demo users).

### `post-deploy/populate_postgres_userdata.py` (optional / legacy)
Not used by the cluster Job anymore. You can still run it locally against `userinfo` if you want the richer **`data/sample_usage.json`** seed instead of the minimal SQL seed.

### `data/sample_usage.json`
Rich JSON profiles used by `populate_postgres_userdata.py` for local or custom seeding.

## Manifests

| File | Resource |
|------|----------|
| `manifests/statefulset.yaml` | Secret, headless Service, StatefulSet (image: `pgvector/pgvector:pg15`) |

The namespace `${NS_PGVECTOR}` is **not** created by this repo; create the OpenShift project / namespace before applying manifests.

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
