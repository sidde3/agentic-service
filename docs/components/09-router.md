# 09 — Router Service

FastAPI intent router that classifies user messages and dispatches them to the appropriate backend.

## What It Does

The router is the main entry point for the chat UI. It:
1. Resolves the user from the `userinfo` database
2. Classifies intent using BERT (or accepts a `predefined_intent`)
3. Routes `MOBILE_USAGE_*` intents to the Agent service
4. Returns stub responses for other intents (greetings, farewells, etc.)
5. Manages session transcripts in Redis
6. Archives completed sessions to PostgreSQL

## Source: `src/router/router.py`

### Request Flow

```
POST /chat → resolve_user → classify_intent → route_to_backend → archive
```

### Intent Classification
- Sends `"History: {context} [SEP] Current: {message}"` to BERT's `/classify` endpoint
- Uses `BERT_CONFIDENCE_THRESHOLD` (default 0.4) to filter low-confidence predictions
- Falls back to `GENERAL_INQUIRY` if below threshold

### Backends
- **Agent backend** — For `MOBILE_USAGE_CHECK_DATA_CURRENT` and `MOBILE_USAGE_COMPARE_DATA_PLAN` intents. Calls `POST {AGENT_API_URL}/recommend` with user context.
- **Stub backend** — For all other intents. Returns canned responses from `stubs.json`.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat` | Main chat endpoint |
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness (checks Redis + Postgres) |
| `GET` | `/config` | Current configuration |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/` | Service info |

### Key Classes
- **`SessionManager`** — Redis-based session store (one JSON blob per user, keyed by `username`)
- **`Archiver`** — Persists sessions to `chat_sessions` table in `userinfo` DB (one row per user, overwritten each turn)

## Manifests

| File | Resource |
|------|----------|
| `deployment.yaml` | Deployment with ConfigMap volume for intents |
| `configmap-router.yaml` | ConfigMap with intent taxonomy |
| `service.yaml` | Service on port 8080 |
| `route.yaml` | Route with edge TLS |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | — | `userinfo` DB connection string |
| `REDIS_HOST` | — | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_PASSWORD` | — | Redis auth |
| `VLLM_API_URL` | — | BERT model route URL |
| `MODEL_NAME` | — | BERT model name |
| `AGENT_API_URL` | — | Agent service internal URL |
| `BERT_CONFIDENCE_THRESHOLD` | `0.4` | Minimum confidence for intent |
| `MAX_TURNS` | `5` | Max conversation turns per session |

## Connections

- **03-models** — BERT for intent classification
- **02-pgvector** — `userinfo` DB for user lookup and chat archival
- **05-redis** — Session transcript storage
- **08-agent** — Forwards agent-routable intents
- **10-frontend** — Called by the chat UI
