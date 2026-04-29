# 01 — RHOAI Prerequisites

One-time cluster-admin setup that enables Red Hat OpenShift AI features and registers MCP servers for GenAI Studio.

## What It Does

1. **`setup/enable-rhoai-features.sh`** — Patches the `DataScienceCluster` and `OdhDashboardConfig` to enable:
   - KServe (Managed mode) for model serving
   - GenAI Studio UI in the RHOAI dashboard
   - Model-as-a-Service capability
   - LlamaStack operator (Managed)
2. **`manifests/gen-ai-mcp-servers-configmap.yaml`** — Registers MCP server URLs so GenAI Studio can discover them in its playground UI.

## Manifests

| File | Resource | Namespace |
|------|----------|-----------|
| `gen-ai-mcp-servers-configmap.yaml` | ConfigMap `gen-ai-aa-mcp-servers` | `redhat-ods-applications` |

The ConfigMap contains JSON entries for each MCP server:
- **Usage-MCP-Server** → `http://usage-mcp-server-v2.${NS_SERVICES}:8000/mcp`
- **HelloWorld-MCP-Server** → `http://helloworld-mcp-server.${NS_SERVICES}:8000/mcp`
- **UserInfo-MCP-Server** → `http://userinfo-mcp-server.${NS_SERVICES}:8000/mcp`

## Configuration

No environment variables. Uses `${NS_SERVICES}` via `scripts/substitute_manifest.py` at deploy time.

## Connections

- Prepares the cluster for **03-models** (KServe), **04-llamastack** (operator)
- ConfigMap URLs point to **06**, **07**, **12** once deployed
