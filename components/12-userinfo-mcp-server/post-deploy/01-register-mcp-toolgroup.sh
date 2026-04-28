#!/bin/bash
# Registers the userinfo MCP server as a toolgroup in LlamaStack.
set -euo pipefail
source "$(dirname "$0")/../../.env.computed" 2>/dev/null || true

LLAMASTACK_URL="${LLAMASTACK_URL:-https://llamastack-${NS_LLAMASTACK:-llamastack}.${CLUSTER_DOMAIN}}"
MCP_INTERNAL="http://userinfo-mcp-server.${NS_SERVICES:-agentic-service}.svc.cluster.local:8000"
TOOLGROUP_ID="userinfo-mcp-server"

echo "==> Registering MCP toolgroup: $TOOLGROUP_ID"
echo "    LlamaStack: $LLAMASTACK_URL"
echo "    MCP endpoint: $MCP_INTERNAL/mcp"

curl -sk -X POST "${LLAMASTACK_URL}/v1/toolgroups" \
  -H "Content-Type: application/json" \
  -d "{
    \"toolgroup_id\": \"${TOOLGROUP_ID}\",
    \"provider_id\": \"model-context-protocol\",
    \"mcp_endpoint\": {
      \"uri\": \"${MCP_INTERNAL}/mcp\"
    }
  }" | python3 -m json.tool 2>/dev/null || echo "(registered)"

echo "==> Verifying tools ..."
curl -sk "${LLAMASTACK_URL}/v1/tools" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
for t in data:
    print(f\"  {t.get('toolgroup_id','?'):30s} -> {t.get('identifier','?')}\")
print(f'Total tools: {len(data)}')
"
