# 08 — Agent Service

FastAPI service that wraps the LlamaStack Agents API, providing mobile plan recommendations using MCP tools and RAG.

## What It Does

Creates LlamaStack agent sessions configured with:
- **MCP toolgroup** (`userinfo-mcp-server`) for live user data queries
- **RAG toolgroup** (`builtin::rag` + vector store) for mobile plan knowledge search
- **Qwen 2.5 7B** as the reasoning LLM

The agent processes user requests through LlamaStack's streaming turn API, extracting the final text response.

## Source Files

### `src/agent/main.py`
FastAPI application with endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/recommend` | Full recommendation (returns JSON with steps + reply) |
| `POST` | `/recommend/pretty` | Same but formatted for display |
| `POST` | `/chat` | Simple chat interface |
| `GET` | `/health` | Health check (verifies LlamaStack connectivity) |
| `GET` | `/` | Service info |

### `src/agent/mobile_plan_agent.py`
Core agent logic:
- **`MobilePlanAgent`** class — singleton pattern via `get_agent_instance()`
- **`_ensure_agent(intent)`** — Creates or reuses a LlamaStack agent session. Configures different toolgroups based on intent (usage_check vs compare_plan)
- **`_create_turn_streaming()`** — Sends user message to LlamaStack's turn API (SSE streaming), parses events to extract tool calls, inference steps, and the final response
- **`get_recommendation()`** / **`get_simple_response()`** — High-level methods for the endpoints

### `src/agent/reranker.py`
Post-retrieval reranker:
- **`Reranker`** class — Calls an external reranker model (e.g. Qwen3-Reranker) via `/v1/rerank` endpoint
- For plan comparison intents, the agent searches the vector store (top-K candidates), sends them to the reranker for cross-encoder reranking, and injects the top-N most relevant plans into the LLM context
- Gracefully degrades: if `RERANKER_URL` or `RERANKER_MODEL` are not set, reranking is skipped

### `src/agent/tools.py`
Tool configuration:
- **`AgentToolConfig`** — Reads `MCP_TOOLGROUP` and `VECTOR_DB_ID` from environment
- **`get_all_toolgroups()`** — Returns MCP + RAG toolgroups for agent creation
- **`validate_tool_configuration()`** — Verifies toolgroup accessibility via LlamaStack

### `src/agent/prompts.py`
System prompts for the agent. Supports file-based overrides via `PROMPTS_MOUNT_PATH` (ConfigMap volume).

## Manifests

| File | Resource |
|------|----------|
| `deployment.yaml` | Deployment with ConfigMap volume for prompts |
| `configmap-prompts.yaml` | ConfigMap `agent-prompts` |
| `service.yaml` | Service on port 8080 |
| `route.yaml` | Route with edge TLS |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLAMA_STACK_ENDPOINT` | — | LlamaStack internal URL |
| `INFERENCE_MODEL` | — | Model identifier (e.g. `vllm-inference/qwen25-7b-instruct`) |
| `VECTOR_DB_ID` | `auto` | Vector store ID for RAG |
| `MCP_TOOLGROUP` | `userinfo-mcp-server` | MCP toolgroup registered in LlamaStack |
| `RERANKER_URL` | — | Reranker endpoint (e.g. `https://.../v1/rerank`). If not set, reranking is disabled |
| `RERANKER_MODEL` | — | Reranker model name (e.g. `Qwen/Qwen3-Reranker-0.6B`) |
| `RERANK_TOP_K` | `20` | Number of candidates to retrieve from vector search |
| `RERANK_TOP_N` | `5` | Number of top results after reranking to include in LLM context |
| `PROMPTS_MOUNT_PATH` | `/app/config/prompts` | Directory for prompt override files |

## Connections

- **04-llamastack** — All requests go through the LlamaStack Agents API
- MCP toolgroup resolves to **12-userinfo-mcp-server** (or **06** depending on registration)
- RAG uses vector store created by **04** post-deploy
