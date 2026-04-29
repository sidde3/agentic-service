#!/bin/bash
# Creates (or discovers) the mobile-plans vector store in Llama Stack and
# exports VECTOR_DB_ID for downstream scripts (ingest, agent deployment).
#
# Idempotent: if a store named VECTOR_STORE_NAME already exists, it reuses it.
set -euo pipefail
source "$(dirname "$0")/../../.env.computed" 2>/dev/null || true

LLAMASTACK_URL="${LLAMASTACK_URL:-https://llamastack-${NS_LLAMASTACK:-agentic-service}.${CLUSTER_DOMAIN}}"
VECTOR_STORE_NAME="${VECTOR_STORE_NAME:-mobile-plans}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-vllm-bge-small/bge-small-en-v15}"
EMBEDDING_DIM="${EMBEDDING_DIM:-384}"

echo "======================================"
echo "Vector Store Setup"
echo "======================================"
echo ""
echo "Llama Stack URL:  $LLAMASTACK_URL"
echo "Store name:       $VECTOR_STORE_NAME"
echo "Embedding model:  $EMBEDDING_MODEL (dim=$EMBEDDING_DIM)"
echo ""

# ── If VECTOR_DB_ID is already a concrete vs_* ID, just verify it ──────
if [[ "${VECTOR_DB_ID:-auto}" != "auto" && "${VECTOR_DB_ID:-}" == vs_* ]]; then
    echo "VECTOR_DB_ID already set to '$VECTOR_DB_ID' — verifying ..."
    VS_CHECK=$(curl -sk "${LLAMASTACK_URL}/v1/vector_stores/${VECTOR_DB_ID}" 2>/dev/null \
      | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
    if [[ "$VS_CHECK" == "$VECTOR_DB_ID" ]]; then
        echo "Verified: vector store exists."
        # Ensure it's in .env.computed
        ENV_COMPUTED="$(dirname "$0")/../../.env.computed"
        if [[ -f "$ENV_COMPUTED" ]]; then
            grep -v '^VECTOR_DB_ID=' "$ENV_COMPUTED" > "${ENV_COMPUTED}.tmp" || true
            mv "${ENV_COMPUTED}.tmp" "$ENV_COMPUTED"
        fi
        echo "VECTOR_DB_ID=$VECTOR_DB_ID" >> "$ENV_COMPUTED"
        echo ""
        exit 0
    fi
    echo "WARNING: Store '$VECTOR_DB_ID' not found. Will create a new one."
fi

# ── Check if a store with this name already exists ─────────────────────
EXISTING_ID=$(curl -sk "${LLAMASTACK_URL}/v1/vector_stores" 2>/dev/null \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for vs in data.get('data', []):
    if vs.get('name') == '${VECTOR_STORE_NAME}':
        print(vs['id'])
        break
" 2>/dev/null || echo "")

if [[ -n "$EXISTING_ID" ]]; then
    echo "Vector store '${VECTOR_STORE_NAME}' already exists: $EXISTING_ID"
    export VECTOR_DB_ID="$EXISTING_ID"
else
    echo "Creating vector store '${VECTOR_STORE_NAME}' ..."
    CREATE_RESP=$(curl -sk -X POST "${LLAMASTACK_URL}/v1/vector_stores" \
      -H "Content-Type: application/json" \
      -d "{
        \"name\": \"${VECTOR_STORE_NAME}\",
        \"embedding_model\": \"${EMBEDDING_MODEL}\",
        \"embedding_dimension\": ${EMBEDDING_DIM},
        \"provider_id\": \"pgvector\"
      }" 2>/dev/null)

    NEW_ID=$(echo "$CREATE_RESP" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('id', ''))" 2>/dev/null || echo "")

    if [[ -z "$NEW_ID" ]]; then
        echo "ERROR: Failed to create vector store."
        echo "Response: $CREATE_RESP"
        exit 1
    fi

    echo "Created vector store: $NEW_ID"
    export VECTOR_DB_ID="$NEW_ID"
fi

# ── Persist for downstream scripts and agent deployment ────────────────
ENV_COMPUTED="$(dirname "$0")/../../.env.computed"
if [[ -f "$ENV_COMPUTED" ]]; then
    # Remove any previous VECTOR_DB_ID line and append the fresh one
    grep -v '^VECTOR_DB_ID=' "$ENV_COMPUTED" > "${ENV_COMPUTED}.tmp" || true
    mv "${ENV_COMPUTED}.tmp" "$ENV_COMPUTED"
fi
echo "VECTOR_DB_ID=$VECTOR_DB_ID" >> "$ENV_COMPUTED"

echo ""
echo "VECTOR_DB_ID=$VECTOR_DB_ID  (written to .env.computed)"
echo ""
