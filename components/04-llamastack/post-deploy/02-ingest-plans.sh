#!/bin/bash
# Ingest mobile plan documents into Llama Stack vector store.
# Requires VECTOR_DB_ID (set by 01-create-vector-store.sh via .env.computed).
set -euo pipefail
source "$(dirname "$0")/../../.env.computed" 2>/dev/null || true

LLAMASTACK_URL="${LLAMASTACK_URL:-https://llamastack-${NS_LLAMASTACK:-llamastack}.${CLUSTER_DOMAIN}}"
VECTOR_STORE_ID="${VECTOR_DB_ID:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/../data"

if [[ -z "$VECTOR_STORE_ID" ]]; then
    echo "ERROR: VECTOR_DB_ID is not set."
    echo "Run 01-create-vector-store.sh first or set VECTOR_DB_ID in env.properties."
    exit 1
fi

echo "======================================"
echo "Ingesting Mobile Plans to Llama Stack"
echo "======================================"
echo ""
echo "Llama Stack URL:  $LLAMASTACK_URL"
echo "Vector Store ID:  $VECTOR_STORE_ID"
echo "Data directory:   $DATA_DIR"
echo ""

# ── Verify the vector store exists ─────────────────────────────────────
STORE_INFO=$(curl -sk "${LLAMASTACK_URL}/v1/vector_stores/${VECTOR_STORE_ID}" 2>/dev/null || echo '{}')
STORE_STATUS=$(echo "$STORE_INFO" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('id', ''))" 2>/dev/null || echo "")

if [[ -z "$STORE_STATUS" ]]; then
    echo "ERROR: Vector store '${VECTOR_STORE_ID}' not found in Llama Stack."
    exit 1
fi
echo "Vector store verified."

# ── Check if files are already ingested (idempotent) ───────────────────
EXISTING_FILES=$(echo "$STORE_INFO" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('file_counts', {}).get('completed', 0))" 2>/dev/null || echo "0")

PLAN_FILES=$(ls "$DATA_DIR"/plan_*.txt 2>/dev/null)
TOTAL=$(echo "$PLAN_FILES" | wc -l | tr -d ' ')

if [[ "$EXISTING_FILES" -ge "$TOTAL" && "$EXISTING_FILES" -gt 0 ]]; then
    echo "Vector store already has $EXISTING_FILES files (>= $TOTAL plan files). Skipping ingestion."
    echo ""
    exit 0
fi

echo "Found $TOTAL plan files to ingest ($EXISTING_FILES already in store)."
echo ""

SUCCESS=0
FAILED=0

for plan_file in $PLAN_FILES; do
    filename=$(basename "$plan_file")
    echo -n "  Uploading $filename ... "

    FILE_ID=$(curl -sk -X POST "${LLAMASTACK_URL}/v1/files" \
      -F "file=@${plan_file}" \
      -F "purpose=vector_store" 2>/dev/null \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)

    if [ -z "$FILE_ID" ]; then
        echo "FAIL (upload)"
        FAILED=$((FAILED + 1))
        continue
    fi

    curl -sk -X POST "${LLAMASTACK_URL}/v1/vector_stores/${VECTOR_STORE_ID}/files" \
      -H "Content-Type: application/json" \
      -d "{\"file_id\": \"$FILE_ID\"}" >/dev/null 2>&1

    echo "OK (file_id=$FILE_ID)"
    SUCCESS=$((SUCCESS + 1))
done

echo ""
echo "Done: $SUCCESS succeeded, $FAILED failed out of $TOTAL."
