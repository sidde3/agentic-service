#!/bin/bash
# Master deployment script — deploys all components in order.
# Usage: bash scripts/deploy-all.sh [--skip-post-deploy]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"
load_config

SKIP_POST_DEPLOY="${1:-}"

echo ""
echo "============================================================"
echo "  Agentic Use Case — Full Deployment"
echo "============================================================"
echo "  Cluster:            $CLUSTER_DOMAIN"
echo "  Services NS:        $NS_SERVICES"
echo "  Vector Ingestion:   ${ENABLE_VECTOR_INGESTION:-true}"
echo "============================================================"

# ── Create the services namespace first (needed by 05-10) ───────────────
oc get ns "$NS_SERVICES" &>/dev/null || oc new-project "$NS_SERVICES" --skip-config-write 2>/dev/null || oc create ns "$NS_SERVICES"

# ── Deploy each component in order ─────────────────────────────────────
COMPONENTS_DIR="$REPO_ROOT/components"

for component_dir in "$COMPONENTS_DIR"/[0-9][0-9]-*/; do
    component_name=$(basename "$component_dir")
    section "Deploying $component_name"

    # 01-rhoai-prereqs: run setup script instead of manifests
    if [[ "$component_name" == "01-rhoai-prereqs" ]]; then
        if [[ -f "$component_dir/setup/enable-rhoai-features.sh" ]]; then
            echo "  Running RHOAI prerequisite setup ..."
            bash "$component_dir/setup/enable-rhoai-features.sh"
        fi
        apply_manifests "$component_dir/manifests"
        echo "  01-rhoai-prereqs READY"
        continue
    fi

    # 03-models: hard prerequisite — must be pre-deployed via OpenShift AI dashboard.
    # Manifests in components/03-models/reference/ are for documentation only.
    # Model names/URLs must be configured in env.properties before running this script.
    if [[ "$component_name" == "03-models" ]]; then
        echo "  Models are a hard prerequisite (see components/03-models/reference/)."
        echo "  Ensure all models are deployed and configured in env.properties."
        echo "  03-models SKIPPED (reference only)"
        continue
    fi

    apply_manifests "$component_dir/manifests"

    # Wait for known deployments/statefulsets
    case "$component_name" in
        02-pgvector)   wait_for_statefulset "pgvector" "$NS_PGVECTOR" ;;
        04-llamastack)
            echo "  Waiting for LlamaStackDistribution to become Ready ..."
            for i in $(seq 1 60); do
                phase=$(oc get llamastackdistribution -n "$NS_LLAMASTACK" -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
                [[ "$phase" == "Ready" ]] && break
                sleep 5
            done
            ;;
        05-redis)              wait_for_deployment "redis" "$NS_SERVICES" ;;
        06-usage-mcp-server)   wait_for_deployment "usage-mcp-server-v2" "$NS_SERVICES" ;;
        07-helloworld-mcp)     wait_for_deployment "helloworld-mcp-server" "$NS_SERVICES" ;;
        08-agent)              wait_for_deployment "agent-service" "$NS_SERVICES" ;;
        09-router)             wait_for_deployment "router-service" "$NS_SERVICES" ;;
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

    # After LlamaStack post-deploy, re-source .env.computed to pick up
    # VECTOR_DB_ID (dynamically set by 01-create-vector-store.sh)
    if [[ "$component_name" == "04-llamastack" ]]; then
        local_computed="$REPO_ROOT/components/.env.computed"
        if [[ -f "$local_computed" ]]; then
            echo "  Re-sourcing .env.computed (VECTOR_DB_ID) ..."
            set -a; source "$local_computed"; set +a
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
smoke_check "Router /health"        "$ROUTER_ROUTE_URL/health"
smoke_check "Agent /health"         "$AGENT_ROUTE_URL/health"
smoke_check "Llama Stack /models"   "$LLAMASTACK_URL/v1/models"

echo ""
echo "  Chat test (usage check):"
printf "  %-30s " "POST /chat"
CHAT_RESPONSE=$(curl -sk -X POST "$ROUTER_ROUTE_URL/chat" \
    -H "Content-Type: application/json" \
    -d '{"user_id":"jessica.thompson@example.com","message":"Check my current data usage","predefined_intent":"MOBILE_USAGE_CHECK_DATA_CURRENT"}' 2>/dev/null || echo "")
if echo "$CHAT_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('reply')" 2>/dev/null; then
    echo "OK (got reply)"
    SMOKE_PASS=$((SMOKE_PASS + 1))
else
    echo "FAIL (no reply)"
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
echo "  Router:      $ROUTER_ROUTE_URL"
echo "  Agent:       $AGENT_ROUTE_URL"
echo "  Llama Stack: $LLAMASTACK_URL"
echo "  Frontend:    Run locally: streamlit run components/10-frontend/src/chat_app.py"
echo ""
echo "  Full test suite:  bash tests/test-all.sh"
echo ""
