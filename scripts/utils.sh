#!/bin/bash
# Shared utility functions for deploy and test scripts.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Load and export env.properties ──────────────────────────────────────
load_config() {
    local config_file="${REPO_ROOT}/config/env.properties"
    if [[ ! -f "$config_file" ]]; then
        echo "ERROR: $config_file not found."
        echo "Copy config/env.properties.example to config/env.properties and fill in your values."
        exit 1
    fi
    set -a
    source "$config_file"
    set +a
    compute_urls
}

# ── Derive computed URLs from base properties ───────────────────────────
compute_urls() {
    export PGVECTOR_HOST="pgvector.${NS_PGVECTOR}.svc.cluster.local"
    export REDIS_HOST="redis.${NS_SERVICES}.svc.cluster.local"
    export LLAMASTACK_URL="https://llamastack-${NS_LLAMASTACK}.${CLUSTER_DOMAIN}"
    export BERT_URL="https://${BERT_MODEL_NAME}-${NS_MODELS}.${CLUSTER_DOMAIN}"
    export AGENT_ROUTE_URL="https://agent-service-${NS_SERVICES}.${CLUSTER_DOMAIN}"
    export ROUTER_ROUTE_URL="https://router-service-${NS_SERVICES}.${CLUSTER_DOMAIN}"
    export AGENT_INTERNAL="http://agent-service.${NS_SERVICES}.svc.cluster.local:8080"
    export MCP_INTERNAL="http://usage-mcp-server-v2.${NS_SERVICES}.svc.cluster.local:8000"
    export LLAMASTACK_INTERNAL="http://llamastack-custom-distribution.${NS_LLAMASTACK}.svc.cluster.local:8321"

    # Write computed vars to a temp file for post-deploy scripts
    cat > "${REPO_ROOT}/components/.env.computed" <<EOF
# Auto-generated — do not edit
PGVECTOR_HOST=$PGVECTOR_HOST
REDIS_HOST=$REDIS_HOST
LLAMASTACK_URL=$LLAMASTACK_URL
LLAMASTACK_INTERNAL=$LLAMASTACK_INTERNAL
BERT_URL=$BERT_URL
AGENT_ROUTE_URL=$AGENT_ROUTE_URL
ROUTER_ROUTE_URL=$ROUTER_ROUTE_URL
AGENT_INTERNAL=$AGENT_INTERNAL
MCP_INTERNAL=$MCP_INTERNAL
EOF
}

# ── Apply a manifest directory with envsubst ────────────────────────────
apply_manifests() {
    local manifest_dir="$1"
    if [[ ! -d "$manifest_dir" ]]; then
        echo "  (no manifests/ directory — skipping)"
        return 0
    fi
    for yaml_file in "$manifest_dir"/*.yaml; do
        [[ -f "$yaml_file" ]] || continue
        echo "  Applying $(basename "$yaml_file") ..."
        envsubst < "$yaml_file" | oc apply -f -
    done
}

# ── Wait for a deployment to roll out ───────────────────────────────────
wait_for_deployment() {
    local deploy_name="$1"
    local namespace="$2"
    local timeout="${3:-180s}"
    echo "  Waiting for deploy/$deploy_name in $namespace ..."
    oc rollout status "deploy/$deploy_name" -n "$namespace" --timeout="$timeout" 2>/dev/null || true
}

# ── Wait for a statefulset ──────────────────────────────────────────────
wait_for_statefulset() {
    local sts_name="$1"
    local namespace="$2"
    local timeout="${3:-180s}"
    echo "  Waiting for statefulset/$sts_name in $namespace ..."
    oc rollout status "statefulset/$sts_name" -n "$namespace" --timeout="$timeout" 2>/dev/null || true
}

# ── Run post-deploy scripts ─────────────────────────────────────────────
run_post_deploy() {
    local post_dir="$1"
    if [[ ! -d "$post_dir" ]]; then
        return 0
    fi
    for script in "$post_dir"/*.sh; do
        [[ -f "$script" ]] || continue
        echo "  Running $(basename "$script") ..."
        bash "$script"
    done
}

# ── Print a section header ──────────────────────────────────────────────
section() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "============================================================"
}
