# 05 — Redis

In-memory data store for session management in the router.

## What It Does

Deploys a single Redis instance used by the router to store conversation transcripts per session. Each session is a Redis list keyed by session ID, with configurable TTL and trim limits.

## Manifests

| File | Resource |
|------|----------|
| `manifests/deployment.yaml` | Deployment `redis`, Service `redis` (port 6379) |

All resources are deployed in `${NS_SERVICES}`.

## Configuration

| Variable | Purpose |
|----------|---------|
| `REDIS_PASSWORD` | Authentication password |

## Connections

- **09-router** — Stores and retrieves session transcripts via `REDIS_HOST` / `REDIS_PASSWORD`
