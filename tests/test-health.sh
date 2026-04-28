#!/bin/bash
# Health checks for all deployed components.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../scripts/utils.sh"
load_config

echo ""
echo "=== Health Checks ==="
echo ""

check() {
    local name="$1" url="$2"
    printf "  %-25s " "$name"
    status=$(curl -sk -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [[ "$status" == "200" ]]; then
        echo "OK ($status)"
    else
        echo "FAIL ($status) — $url"
    fi
}

check "Router /health"        "$ROUTER_ROUTE_URL/health"
check "Router /ready"         "$ROUTER_ROUTE_URL/ready"
check "Agent /health"         "$AGENT_ROUTE_URL/health"
check "Llama Stack /models"   "$LLAMASTACK_URL/v1/models"
check "BERT /classify"        "$BERT_URL/classify"

echo ""
echo "=== Pod Status ==="
echo ""
for ns in "$NS_SERVICES" "$NS_LLAMASTACK" "$NS_PGVECTOR"; do
    echo "--- $ns ---"
    oc get pods -n "$ns" --no-headers 2>/dev/null | while read -r line; do echo "  $line"; done
done
