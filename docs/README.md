# Documentation Index

## Overview

- [Architecture](architecture.md) — System design, data flow, database layout, namespace structure
- [Deployment Guide](deployment-guide.md) — Step-by-step deployment instructions
- [Troubleshooting](troubleshooting.md) — Common issues and solutions

## Component Documentation

| # | Component | Description |
|---|-----------|-------------|
| 00 | [RHOAI Prerequisites](components/00-rhoai-prereqs.md) | Cluster setup, GenAI Studio config |
| 02 | [pgvector](components/02-pgvector.md) | PostgreSQL + pgvector, DB init jobs |
| 03 | [Models](components/03-models.md) | Qwen, BERT, BGE-small InferenceServices |
| 04 | [LlamaStack](components/04-llamastack.md) | LlamaStack distribution, agents, vector I/O |
| 05 | [Redis](components/05-redis.md) | Session store for router |
| 06 | [Usage MCP Server](components/06-usage-mcp-server.md) | Direct SQL-based usage data MCP |
| 07 | [HelloWorld MCP](components/07-helloworld-mcp.md) | Demo MCP server |
| 08 | [Agent](components/08-agent.md) | Mobile plan agent (LlamaStack + MCP + RAG) |
| 09 | [Router](components/09-router.md) | Intent classification and routing |
| 10 | [Frontend](components/10-frontend.md) | Streamlit chat UI |
| 11 | [UserInfo API](components/11-userinfo-api.md) | REST API over userinfo DB |
| 12 | [UserInfo MCP Server](components/12-userinfo-mcp-server.md) | MCP proxy to UserInfo API |
