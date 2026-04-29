# 08 — Agent Service

FastAPI service that wraps the LlamaStack Agents API, providing mobile plan recommendations using MCP tools and RAG.

## What It Does

Creates LlamaStack agent sessions configured with:
- **MCP toolgroup** (`userinfo-mcp-server`) for live user data queries
- **RAG toolgroup** (`builtin::rag` + vector store) for mobile plan knowledge search
- **Qwen 2.5 7B** as the reasoning LLM
- **Optional reranker** (e.g. Qwen3-Reranker) to re-score vector search results before the LLM sees them

The agent processes user requests through LlamaStack's non-streaming turn API, returning the final text response.

## Source Files

### `src/agent/server.py`
FastAPI application containing the agent logic:

- **`_api(method, path)`** — Calls the LlamaStack REST API
- **`_get_or_create_agent(intent)`** — Creates or reuses a LlamaStack agent. Configures different toolgroups based on intent:
  - `MOBILE_USAGE_CHECK_DATA_CURRENT` → MCP tools only
  - `MOBILE_USAGE_COMPARE_DATA_PLAN` → MCP + RAG tools
- **`_search_and_rerank(query)`** — Searches the vector store and reranks results via the external reranker endpoint. Returns formatted context to prepend to the user message. Skipped when reranking is disabled.
- **`_run_turn(agent_id, session_id, messages)`** — Sends messages to the agent (non-streaming) and extracts the reply and tool call summary
- **`get_recommendation()`** — Main logic: create agent → open session → search & rerank (if enabled) → build message → run turn → return result

Endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/recommend` | Personalised recommendation (returns JSON with reply + tool summary) |
| `GET` | `/health` | Health check (verifies LlamaStack connectivity) |
| `GET` | `/` | Service info |

### `src/agent/reranker.py`
Simple reranker module:
- **`is_enabled()`** — Returns `True` if `RERANK_ENABLED=true` and URL/model are set
- **`rerank(query, documents)`** — Calls the external `/v1/rerank` endpoint, returns top-N scored results. Falls back to original order on failure.

### `src/agent/prompts.py`
System prompts for the agent — plain string constants, one per intent:
- `MOBILE_PLAN_AGENT_PROMPT` — compare/recommend plans (MCP + RAG)
- `MOBILE_USAGE_CHECK_PROMPT` — check current usage (MCP only)
- Error messages: `ERROR_USER_NOT_FOUND`, `ERROR_TOOLS_UNAVAILABLE`

## Manifests

| File | Resource |
|------|----------|
| `deployment.yaml` | Deployment |
| `service.yaml` | Service on port 8080 |
| `route.yaml` | Route with edge TLS |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLAMA_STACK_ENDPOINT` | — | LlamaStack internal URL |
| `INFERENCE_MODEL` | — | Model identifier (e.g. `vllm-inference/qwen25-7b-instruct`) |
| `VECTOR_DB_ID` | — | Vector store ID for RAG |
| `MCP_TOOLGROUP` | `userinfo-mcp-server` | MCP toolgroup registered in LlamaStack |
| `RERANK_ENABLED` | `false` | Set to `true` to enable reranking |
| `RERANKER_URL` | — | Reranker endpoint (e.g. `https://.../v1/rerank`) |
| `RERANKER_MODEL` | — | Reranker model name — must match the model ID from `/v1/models` (e.g. `qwen3-reranker-06b`) |
| `RERANK_TOP_K` | `20` | Number of candidates to retrieve from vector search |
| `RERANK_TOP_N` | `5` | Number of top results after reranking to include in LLM context |

## Connections

- **04-llamastack** — All requests go through the LlamaStack Agents API
- MCP toolgroup resolves to **12-userinfo-mcp-server**
- RAG uses vector store created by **04** post-deploy
