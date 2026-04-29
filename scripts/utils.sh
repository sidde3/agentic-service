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
    # Extract short model name from INFERENCE_MODEL (e.g. "qwen25-7b-instruct" from "vllm-inference/qwen25-7b-instruct")
    local vllm_model_name="${INFERENCE_MODEL##*/}"

    # LlamaStackDistribution / rh-dev containerSpec (matches RHOAI working CR)
    export LLS_INFERENCE_MODEL_ID="${LLS_INFERENCE_MODEL_ID:-${vllm_model_name}}"
    export POSTGRES_HOST="${POSTGRES_HOST:-pgvector.${NS_PGVECTOR}.svc.cluster.local}"
    export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
    export POSTGRES_DB="${POSTGRES_DB:-llamastack}"
    export POSTGRES_USER="${POSTGRES_USER:-${PG_LLAMASTACK_USER}}"
    export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-${PG_LLAMASTACK_PASSWORD}}"
    # Public Route URLs — set VLLM_URL / VLLM_EMBEDDING_URL in env.properties if names differ from this pattern
    export VLLM_URL="${VLLM_URL:-https://${vllm_model_name}-${NS_MODELS}.${CLUSTER_DOMAIN}/v1}"
    export VLLM_EMBEDDING_URL="${VLLM_EMBEDDING_URL:-https://${EMBEDDING_MODEL_NAME}-${NS_MODELS}.${CLUSTER_DOMAIN}/v1}"
    export VLLM_TLS_VERIFY="${VLLM_TLS_VERIFY:-false}"
    export VLLM_EMBEDDING_TLS_VERIFY="${VLLM_EMBEDDING_TLS_VERIFY:-false}"
    export EMBEDDING_PROVIDER_MODEL_ID="${EMBEDDING_PROVIDER_MODEL_ID:-${EMBEDDING_MODEL_NAME}}"
    export ENABLE_PGVECTOR="${ENABLE_PGVECTOR:-true}"
    export PGVECTOR_PORT="${PGVECTOR_PORT:-5432}"
    export LLAMASTACK_DISTRIBUTION_NAME="${LLAMASTACK_DISTRIBUTION_NAME:-rh-dev}"
    export LLAMASTACK_CPU_REQUEST="${LLAMASTACK_CPU_REQUEST:-250m}"
    export LLAMASTACK_MEMORY_REQUEST="${LLAMASTACK_MEMORY_REQUEST:-500Mi}"
    export LLAMASTACK_CPU_LIMIT="${LLAMASTACK_CPU_LIMIT:-4}"
    export LLAMASTACK_MEMORY_LIMIT="${LLAMASTACK_MEMORY_LIMIT:-12Gi}"

    export PGVECTOR_HOST="pgvector.${NS_PGVECTOR}.svc.cluster.local"
    export REDIS_HOST="redis.${NS_SERVICES}.svc.cluster.local"
    export LLAMASTACK_URL="https://llamastack-${NS_LLAMASTACK}.${CLUSTER_DOMAIN}"
    export LLAMASTACK_INTERNAL="http://llamastack-custom-distribution.${NS_LLAMASTACK}.svc.cluster.local:8321"
    export BERT_URL="https://${BERT_MODEL_NAME}-${NS_MODELS}.${CLUSTER_DOMAIN}"
    export RERANKER_URL="https://${RERANKER_MODEL}-${NS_MODELS}.${CLUSTER_DOMAIN}/v1/rerank"
    export VLLM_INTERNAL_URL="http://${vllm_model_name}-predictor.${NS_MODELS}.svc.cluster.local/v1"
    export EMBEDDING_INTERNAL_URL="http://${EMBEDDING_MODEL_NAME}-predictor.${NS_MODELS}.svc.cluster.local/v1"
    export AGENT_ROUTE_URL="https://agent-service-${NS_SERVICES}.${CLUSTER_DOMAIN}"
    export ROUTER_ROUTE_URL="https://router-service-${NS_SERVICES}.${CLUSTER_DOMAIN}"
    export AGENT_INTERNAL="http://agent-service.${NS_SERVICES}.svc.cluster.local:8080"
    export MCP_INTERNAL="http://usage-mcp-server-v2.${NS_SERVICES}.svc.cluster.local:8000"
    export USERINFO_API_URL="http://userinfo-api.${NS_SERVICES}.svc.cluster.local:8000"

    # Write computed vars to a temp file for post-deploy scripts
    cat > "${REPO_ROOT}/components/.env.computed" <<EOF
# Auto-generated — do not edit
PGVECTOR_HOST=$PGVECTOR_HOST
REDIS_HOST=$REDIS_HOST
LLAMASTACK_URL=$LLAMASTACK_URL
LLAMASTACK_INTERNAL=$LLAMASTACK_INTERNAL
BERT_URL=$BERT_URL
RERANKER_URL=$RERANKER_URL
VLLM_INTERNAL_URL=$VLLM_INTERNAL_URL
EMBEDDING_INTERNAL_URL=$EMBEDDING_INTERNAL_URL
VLLM_URL=$VLLM_URL
VLLM_EMBEDDING_URL=$VLLM_EMBEDDING_URL
AGENT_ROUTE_URL=$AGENT_ROUTE_URL
ROUTER_ROUTE_URL=$ROUTER_ROUTE_URL
AGENT_INTERNAL=$AGENT_INTERNAL
MCP_INTERNAL=$MCP_INTERNAL
USERINFO_API_URL=$USERINFO_API_URL
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
