# AI Agentic Use Case

Multi-turn customer-service chat system powered by fine-tuned BERT intent classification and an LLM-driven agentic workflow on **Red Hat OpenShift AI**.

A user messages through a **Streamlit Chat UI**. The **Router** classifies the message via a fine-tuned **PhayaThai BERT** model. Data-plan intents are forwarded to an **Agent** that orchestrates **LlamaStack** — combining MCP tools (live user data via UserInfo API) with pgvector RAG (plan catalog search) and **Qwen3-Reranker** for post-retrieval reranking — and returns a personalised recommendation powered by **Qwen 2.5 7B**.

## Components

| # | Component | Description | Docs |
|---|-----------|-------------|------|
| 01 | RHOAI Prerequisites | KServe, GenAI Studio, LlamaStack operator, MCP ConfigMap | [docs](docs/components/01-rhoai-prereqs.md) |
| 02 | pgvector | PostgreSQL + pgvector: single Job `db-init` (DBs, roles, userinfo tables + seed) | [docs](docs/components/02-pgvector.md) |
| 03 | Models | Qwen 2.5 7B (GPU), BERT (CPU), BGE-small (CPU) | [docs](docs/components/03-models.md) |
| 04 | LlamaStack | Inference, agents, vector I/O, MCP tool runtime | [docs](docs/components/04-llamastack.md) |
| 05 | Redis | Session store for router | [docs](docs/components/05-redis.md) |
| 06 | Usage MCP Server | Direct SQL-based mobile usage MCP tools | [docs](docs/components/06-usage-mcp-server.md) |
| 07 | HelloWorld MCP | Demo MCP server for GenAI Studio testing | [docs](docs/components/07-helloworld-mcp.md) |
| 08 | Agent | LlamaStack agent with MCP + RAG toolgroups | [docs](docs/components/08-agent.md) |
| 09 | Router | BERT intent classification + routing | [docs](docs/components/09-router.md) |
| 10 | Frontend | Streamlit chat UI (runs locally) | [docs](docs/components/10-frontend.md) |
| 11 | UserInfo API | REST API over userinfo database | [docs](docs/components/11-userinfo-api.md) |
| 12 | UserInfo MCP Server | MCP proxy to UserInfo API | [docs](docs/components/12-userinfo-mcp-server.md) |

## Deployment Model

All application workloads (pgvector, LlamaStack, Redis, Agent, Router, MCP servers) deploy into a **single namespace**. Only AI models live in a separate namespace, pre-deployed via the OpenShift AI dashboard.

## Quick Start

```bash
# 1. Configure
cp config/env.properties.example config/env.properties
# Edit with your cluster domain, credentials, image tags
# NS_PGVECTOR, NS_LLAMASTACK, NS_SERVICES should all be the same namespace

# 2. Create that namespace on the cluster (not done by deploy scripts)
set -a && source config/env.properties && set +a
oc new-project "${NS_SERVICES}" --skip-config-write 2>/dev/null || true

# 3. Deploy everything
bash scripts/deploy-all.sh

# 4. Run the chat UI
export ROUTER_URL="https://router-service-${NS_SERVICES}.${CLUSTER_DOMAIN}"
streamlit run components/10-frontend/src/chat_app.py
```

See the full [Deployment Guide](docs/deployment-guide.md) for details.

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design, data flow, database layout |
| [Deployment Guide](docs/deployment-guide.md) | Step-by-step deployment instructions |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |
| [Component Docs](docs/README.md) | Per-component code walkthroughs and config |

## Tech Stack

- **Platform**: Red Hat OpenShift AI with KServe
- **LLM Orchestration**: LlamaStack (MCP + pgvector + Agents API)
- **Models**: Qwen 2.5 7B Instruct AWQ (vLLM), PhayaThai BERT (intent), BGE-small (embeddings), Qwen3-Reranker (reranking)
- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, asyncpg, httpx
- **Session Store**: Redis
- **Database**: PostgreSQL 15 + pgvector
- **Frontend**: Streamlit
- **Vector Ingestion**: Kubeflow Pipelines (OpenShift AI)
- **Images**: `quay.io/sidde3/*`

## Repository Structure

```
ais-agentic-usecase/
├── config/                    # env.properties (central configuration)
├── components/
│   ├── 01-rhoai-prereqs/      # Cluster-admin RHOAI setup
│   ├── 02-pgvector/           # PostgreSQL + pgvector + K8s Jobs
│   ├── 03-models/             # KServe InferenceServices (Qwen, BERT, BGE)
│   ├── 04-llamastack/         # LlamaStack distribution + plan data
│   ├── 05-redis/              # Redis
│   ├── 06-usage-mcp-server/   # Usage data MCP server
│   ├── 07-helloworld-mcp/     # Demo MCP server
│   ├── 08-agent/              # Agent service
│   ├── 09-router/             # Intent router
│   ├── 10-frontend/           # Streamlit chat UI
│   ├── 11-userinfo-api/       # UserInfo REST API
│   └── 12-userinfo-mcp-server/ # UserInfo MCP server
├── scripts/                   # deploy-all.sh, utils.sh
├── docs/                      # Architecture, deployment, component docs
├── tests/                     # Health and integration tests
└── archive/                   # Old code and docs (reference only)
```
