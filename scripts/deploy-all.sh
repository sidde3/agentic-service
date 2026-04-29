#!/bin/bash
# Master deployment script — deploys all components in dependency-aware order.
# Usage: bash scripts/deploy-all.sh [--skip-post-deploy]
#
# Sequence (numeric sort is not used). This script only deploys:
#   02 PGVector (+ DB Jobs) → 04 LlamaStack (+ vector ingestion)
#   → 11 userinfo-api → 12 userinfo-mcp (+ MCP registration) → 08 agent
# Cluster operators / RHOAI prereqs (01), models, router, redis, other MCPs, frontend, etc. are out of scope here.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"
load_config

SKIP_POST_DEPLOY="${1:-}"

# Explicit order — do not rely on lexical directory sort.
DEPLOY_COMPONENT_ORDER=(
    02-pgvector
    04-llamastack
    11-userinfo-api
    12-userinfo-mcp-server
    08-agent
)

echo ""
echo "============================================================"
echo "  Agentic Use Case — Full Deployment"
echo "============================================================"
echo "  Cluster:            $CLUSTER_DOMAIN"
echo "  Namespace:          $NS_SERVICES"
echo "  Models NS:          $NS_MODELS (hard prerequisite)"
echo "  Vector Ingestion:   ${ENABLE_VECTOR_INGESTION:-true}"
echo "============================================================"

# Namespace must already exist (configure NS_* in config/env.properties).

COMPONENTS_DIR="$REPO_ROOT/components"
local_computed="$REPO_ROOT/components/.env.computed"

for component_name in "${DEPLOY_COMPONENT_ORDER[@]}"; do
    component_dir="${COMPONENTS_DIR}/${component_name}"
    if [[ ! -d "$component_dir" ]]; then
        echo "WARNING: missing component directory $component_dir — skipping"
        continue
    fi

    section "Deploying $component_name"

    # Agent manifest needs VECTOR_DB_ID from LlamaStack post-deploy.
    if [[ "$component_name" == "08-agent" && -f "$local_computed" ]]; then
        echo "  Re-sourcing .env.computed (VECTOR_DB_ID) before agent manifests ..."
        set -a
        # shellcheck source=/dev/null
        source "$local_computed"
        set +a
    fi

    apply_manifests "$component_dir/manifests"

    # Wait for known deployments/statefulsets
    case "$component_name" in
        02-pgvector)            wait_for_statefulset "pgvector" "$NS_PGVECTOR" ;;
        04-llamastack)
            echo "  Waiting for LlamaStackDistribution to become Ready ..."
            for _ in $(seq 1 60); do
                phase=$(oc get llamastackdistribution -n "$NS_LLAMASTACK" -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
                [[ "$phase" == "Ready" ]] && break
                sleep 5
            done
            ;;
        08-agent)               wait_for_deployment "agent-service" "$NS_SERVICES" ;;
        11-userinfo-api)       wait_for_deployment "userinfo-api" "$NS_SERVICES" ;;
        12-userinfo-mcp-server) wait_for_deployment "userinfo-mcp-server" "$NS_SERVICES" ;;
    esac

    # Post-deploy scripts
    if [[ "$SKIP_POST_DEPLOY" != "--skip-post-deploy" ]]; then
        if [[ "$component_name" == "04-llamastack" && "${ENABLE_VECTOR_INGESTION:-true}" != "true" ]]; then
            echo "  ENABLE_VECTOR_INGESTION=${ENABLE_VECTOR_INGESTION:-true} — skipping vector store creation and plan ingestion."
            echo "  Only running 03-verify.sh ..."
            if [[ -f "$component_dir/post-deploy/03-verify.sh" ]]; then
                bash "$component_dir/post-deploy/03-verify.sh"
            fi
        else
            run_post_deploy "$component_dir/post-deploy"
        fi
    fi

    # After LlamaStack post-deploy, re-source .env.computed to pick up VECTOR_DB_ID
    if [[ "$component_name" == "04-llamastack" ]]; then
        if [[ -f "$local_computed" ]]; then
            echo "  Re-sourcing .env.computed (VECTOR_DB_ID) ..."
            set -a
            # shellcheck source=/dev/null
            source "$local_computed"
            set +a
        fi
    fi

    echo "  $component_name READY"
done

# ── Smoke Test ──────────────────────────────────────────────────────────
section "Smoke Test"
SMOKE_PASS=0
SMOKE_FAIL=0

smoke_check() {
    local name="$1" url="$2"
    printf "  %-30s " "$name"
    local status
    status=$(curl -sk -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [[ "$status" == "200" ]]; then
        echo "OK ($status)"
        SMOKE_PASS=$((SMOKE_PASS + 1))
    else
        echo "FAIL ($status)"
        SMOKE_FAIL=$((SMOKE_FAIL + 1))
    fi
}

echo ""
echo "  Health checks:"
smoke_check "Agent /health"         "$AGENT_ROUTE_URL/health"
smoke_check "Llama Stack /models"   "$LLAMASTACK_URL/v1/models"

echo ""
echo "  Agent workflow (RAG + userinfo MCP via POST /recommend):"
printf "  %-30s " "POST /recommend"
RECOMMEND_RESPONSE=$(curl -sk --max-time 300 -X POST "${AGENT_ROUTE_URL}/recommend" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"jessica.thompson@example.com","query":"Compare my current plan with alternatives. Use my account and usage, search the plan catalog, then recommend.","intent":"MOBILE_USAGE_COMPARE_DATA_PLAN"}' \
    2>/dev/null || echo "")
if echo "$RECOMMEND_RESPONSE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('status') == 'success' and not d.get('has_errors'), d
assert (d.get('reply') or '').strip(), 'empty reply'
tools = list(d.get('tool_call_summary') or [])
has_rag = 'knowledge_search' in tools
has_userinfo_mcp = any(
    t.startswith('get_') or 'user_info' in t.lower() or 'subscription' in t.lower()
    for t in tools
)
assert has_rag and has_userinfo_mcp, f'expected vector RAG + userinfo MCP tools, got {tools!r}'
" 2>/dev/null; then
    echo "OK (reply + tools)"
    SMOKE_PASS=$((SMOKE_PASS + 1))
else
    echo "FAIL (see agent logs / model availability)"
    SMOKE_FAIL=$((SMOKE_FAIL + 1))
fi

echo ""
echo "  Results: $SMOKE_PASS passed, $SMOKE_FAIL failed"

if [[ "$SMOKE_FAIL" -gt 0 ]]; then
    echo ""
    echo "  WARNING: Some smoke tests failed. Check component logs."
fi

# ── Summary ─────────────────────────────────────────────────────────────
section "Deployment Complete"
echo ""
echo "  Agent:       $AGENT_ROUTE_URL"
echo "  Llama Stack: $LLAMASTACK_URL"
echo ""
echo "  Full test suite:  bash tests/test-all.sh"
echo ""
