# Deployment Guide

Step-by-step instructions for deploying the AI Agentic Use Case on an OpenShift cluster with Red Hat OpenShift AI.

## Prerequisites

- OpenShift 4.14+ cluster with cluster-admin access
- Red Hat OpenShift AI operator installed (with LlamaStack operator support)
- `oc` CLI authenticated to the cluster
- At least 1 NVIDIA GPU (T4/L40) for Qwen model serving
- `envsubst` available (part of `gettext`)

### Required AI Models (must be pre-deployed)

Three AI models must be deployed as KServe InferenceServices **before** running `deploy-all.sh`. The script does not create these models — it only verifies they are `Ready`. Reference manifests are provided in `components/03-models/reference/`.

1. **`finetuned-phayathai-bert`** — Fine-tuned BERT model for intent classification. The **Router** sends every user message to this model to determine the intent before routing to the appropriate handler.

2. **`qwen25-7b-instruct`** — Decoder LLM for reasoning and tool calling. **LlamaStack** uses this model to power the agentic loop — selecting tools, interpreting results, and generating plan recommendations.

3. **`bge-small-en-v15`** — Embedding model for semantic search. **LlamaStack** uses this model to generate vector embeddings when ingesting plan documents and when the agent performs `knowledge_search` against the plan catalog.

4. **`qwen3-reranker-06b`** (optional) — Cross-encoder reranker model. The **Agent** calls this model to rerank vector search results before passing them to the LLM, improving plan recommendation quality. If not deployed, the agent falls back to raw vector similarity ranking.

> **Note:** `RERANKER_MODEL` in `env.properties` must match the model ID reported by the vLLM endpoint (`curl -sk <RERANKER_URL_BASE>/v1/models`). This is the **InferenceService name** (e.g. `qwen3-reranker-06b`), not the HuggingFace model path (e.g. `Qwen/Qwen3-Reranker-0.6B`).

Deploy these via the OpenShift AI dashboard or by manually applying the reference manifests in `components/03-models/reference/`.

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> && cd ais-agentic-usecase

# 2. Create your configuration
cp config/env.properties.example config/env.properties
# Edit config/env.properties with your cluster values

# 3. Deploy everything
bash scripts/deploy-all.sh
```

## Configuration

Copy `config/env.properties.example` to `config/env.properties` and set:

### Required Values

| Variable | Example | Description |
|----------|---------|-------------|
| `CLUSTER_DOMAIN` | `apps.ocp.example.com` | OpenShift apps domain |
| `NS_PGVECTOR` | `pg-vector` | pgvector namespace |
| `NS_MODELS` | `intent-classification-sidd` | Models namespace |
| `NS_LLAMASTACK` | `llamastack` | LlamaStack namespace |
| `NS_SERVICES` | `agentic-service` | Services namespace |
| `PGVECTOR_USER` | `appuser` | pgvector superuser |
| `PGVECTOR_PASSWORD` | — | pgvector superuser password |
| `PG_USERINFO_USER` | `user_info` | userinfo DB role |
| `PG_USERINFO_PASSWORD` | — | userinfo DB password |
| `PG_LLAMASTACK_USER` | `llamastack` | llamastack DB role |
| `PG_LLAMASTACK_PASSWORD` | — | llamastack DB password |
| `REDIS_PASSWORD` | — | Redis authentication |

### Image References

All images are pre-built and hosted on `quay.io/sidde3/`:

| Variable | Image |
|----------|-------|
| `IMAGE_AGENT` | `quay.io/sidde3/agent-service:latest` |
| `IMAGE_ROUTER` | `quay.io/sidde3/router-service:latest` |
| `IMAGE_USAGE_MCP` | `quay.io/sidde3/usage-mcp-server:latest` |
| `IMAGE_HELLO_MCP` | `quay.io/sidde3/hello-mcp-server:latest` |
| `IMAGE_USERINFO_API` | `quay.io/sidde3/userinfo-api:latest` |
| `IMAGE_USERINFO_MCP` | `quay.io/sidde3/userinfo-api-mcp:latest` |

## Deployment Order

The `deploy-all.sh` script processes components in numeric order:

### Phase 1: Infrastructure

1. **01-rhoai-prereqs** — Enables KServe, GenAI Studio, LlamaStack operator. Registers MCP servers in the dashboard.
2. **02-pgvector** — Deploys PostgreSQL StatefulSet. Post-deploy: K8s Jobs create databases (`userinfo`, `llamastack`, `pgvector`) and seed sample data.
3. **03-models** — Verifies that the three pre-deployed InferenceServices (Qwen, BERT, BGE-small) are `Ready`. Does not apply any manifests — reference manifests are in `components/03-models/reference/`.

### Phase 2: AI Platform

4. **04-llamastack** — Deploys LlamaStackDistribution with full `run.yaml` config. Post-deploy: creates vector store, ingests plan documents.
5. **05-redis** — Deploys Redis for session management.

### Phase 3: Application Services

6. **06-usage-mcp-server** — Deploys usage MCP server. Post-deploy: registers toolgroup in LlamaStack.
7. **07-helloworld-mcp** — Deploys demo MCP server.
8. **08-agent** — Deploys agent service (connects to LlamaStack).
9. **09-router** — Deploys router service (connects to BERT, Redis, Agent, Postgres).

### Phase 4: UserInfo Stack

10. **11-userinfo-api** — Deploys REST API over userinfo DB.
11. **12-userinfo-mcp-server** — Deploys MCP proxy to UserInfo API.

### Phase 5: Frontend

12. **10-frontend** — No cluster deployment. Run locally:
    ```bash
    export ROUTER_URL=https://router-service-agentic-service.apps.your-cluster.com
    streamlit run components/10-frontend/src/chat_app.py
    ```

## Smoke Tests

After deployment, `deploy-all.sh` automatically runs:
- Health checks on Router, Agent, and LlamaStack
- A test chat request through the full pipeline

## Manual Verification

```bash
# Check all pods
oc get pods -n ${NS_SERVICES}
oc get pods -n ${NS_PGVECTOR}
oc get pods -n ${NS_MODELS}
oc get pods -n ${NS_LLAMASTACK}

# Check InferenceServices
oc get inferenceservices -n ${NS_MODELS}

# Check LlamaStack
oc get llamastackdistribution -n ${NS_LLAMASTACK}

# Test router health
curl -sk https://router-service-${NS_SERVICES}.${CLUSTER_DOMAIN}/health

# Test a chat request
curl -sk -X POST https://router-service-${NS_SERVICES}.${CLUSTER_DOMAIN}/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"jessica.thompson@example.com","message":"Check my current data usage"}'
```

## Selective Deployment

To deploy individual components:

```bash
source scripts/utils.sh
load_config

# Apply manifests for a specific component
apply_manifests components/08-agent/manifests

# Run post-deploy scripts
run_post_deploy components/04-llamastack/post-deploy
```

## Skipping Post-Deploy

```bash
bash scripts/deploy-all.sh --skip-post-deploy
```

This deploys all manifests but skips database seeding, vector store creation, and toolgroup registration. Useful when redeploying to an existing cluster.

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues and solutions.
