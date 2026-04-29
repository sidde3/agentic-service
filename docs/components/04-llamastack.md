# 04 — LlamaStack

LlamaStack distribution providing a unified API layer for inference, agents, vector I/O, tool runtime, and storage.

## What It Does

Deploys a **LlamaStackDistribution** custom resource managed by the LlamaStack operator. The distribution configuration is supplied via the `llamastack-user-config` ConfigMap containing a full `run.yaml`.

## APIs Exposed

The distribution enables these APIs (all under the LlamaStack route):
- **Agents** — Create/manage agent sessions with tool calling
- **Inference** — Chat completions, embeddings (proxied to vLLM)
- **Vector I/O** — Vector store CRUD and search (backed by pgvector)
- **Tool Runtime** — MCP provider, RAG runtime, web search
- **Files** — File upload for RAG ingestion
- Plus: batches, datasetio, eval, safety, scoring

## Inference Providers

| Provider ID | Type | Backend |
|------------|------|---------|
| `vllm-inference` | `remote::vllm` | Qwen 2.5 7B (GPU) |
| `vllm-bge-small` | `remote::vllm` | BGE-small-en-v1.5 (CPU) |
| `sentence-transformers` | `inline::sentence-transformers` | all-MiniLM-L6-v2 (in-process) |

## Registered Models

| Model ID | Provider | Type | Dimensions |
|----------|----------|------|------------|
| `qwen25-7b-instruct` | `vllm-inference` | LLM | — |
| `llama32-3b` | `vllm-inference` | LLM | — |
| `bge-small-en-v15` | `vllm-bge-small` | Embedding | 384 |
| `all-MiniLM-L6-v2` | `sentence-transformers` | Embedding | 384 |
| `nomic-ai/nomic-embed-text-v1.5` | `sentence-transformers` | Embedding | 768 |

## Post-Deploy Scripts

1. **`01-create-vector-store.sh`** — Creates (or reuses) a vector store named `mobile-plans` via `/v1/vector_stores`. Writes `VECTOR_DB_ID` to `components/.env.computed`.
2. **`02-ingest-plans.sh`** — Uploads `data/plan_*.txt` files via `/v1/files` and attaches them to the vector store. Idempotent based on file count.
3. **`03-verify.sh`** — Queries `/v1/models`, `/v1/toolgroups`, `/v1/vector_stores`, `/v1/providers` to verify setup.

## Manifests

| File | Resource |
|------|----------|
| `llamastack-distribution.yaml` | LlamaStackDistribution CR |
| `llamastack-user-config.yaml` | ConfigMap with `run.yaml` |

The namespace `${NS_LLAMASTACK}` is **not** created here; it must already exist.

## Configuration

| Variable | Purpose |
|----------|---------|
| `NS_LLAMASTACK` | Target namespace |
| `NS_MODELS` | Models namespace (for vLLM URLs in run.yaml) |
| `NS_PGVECTOR` | pgvector namespace (for DB host) |
| `VLLM_INTERNAL_URL` | Qwen predictor internal URL |
| `PGVECTOR_*` | pgvector DB credentials |
| `PG_LLAMASTACK_*` | llamastack DB credentials |

## Connections

- **03-models**: Qwen (inference), BGE-small (embeddings)
- **02-pgvector**: `llamastack` DB (state), `pgvector` DB (vectors)
- **06/12**: MCP servers registered as toolgroups
- **08-agent**: Primary consumer via Agents API
