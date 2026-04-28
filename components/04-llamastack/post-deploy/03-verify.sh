#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/../../.env.computed" 2>/dev/null || true

LLAMASTACK_URL="${LLAMASTACK_URL:-https://llamastack-${NS_LLAMASTACK:-llamastack}.${CLUSTER_DOMAIN}}"

echo "==> Llama Stack verification: $LLAMASTACK_URL"

echo ""
echo "--- Models ---"
curl -sk "${LLAMASTACK_URL}/v1/models" | python3 -c "
import sys, json
for m in json.load(sys.stdin).get('data', []):
    print(f\"  {m.get('identifier','?'):40s} type={m.get('model_type','?')}\")" 2>/dev/null

echo ""
echo "--- Tool Groups ---"
curl -sk "${LLAMASTACK_URL}/v1/toolgroups" | python3 -c "
import sys, json
for tg in json.load(sys.stdin).get('data', []):
    print(f\"  {tg.get('identifier','?'):30s} provider={tg.get('provider_id','?')}\")" 2>/dev/null

echo ""
echo "--- Vector Stores ---"
curl -sk "${LLAMASTACK_URL}/v1/vector_stores" | python3 -c "
import sys, json
for vs in json.load(sys.stdin).get('data', []):
    print(f\"  {vs.get('id','?'):40s}\")" 2>/dev/null

echo ""
echo "--- Providers health ---"
curl -sk "${LLAMASTACK_URL}/v1/providers" | python3 -c "
import sys, json
for p in json.load(sys.stdin):
    h = p.get('health',{})
    print(f\"  {p.get('api','?'):12s} {p.get('provider_id','?'):30s} {h.get('status','?')}\")" 2>/dev/null

echo ""
echo "==> Verification complete."
