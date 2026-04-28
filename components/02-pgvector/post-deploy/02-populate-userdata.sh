#!/bin/bash
# Populates the userinfo database with sample user data via a Kubernetes Job.
# The Job runs a Python container inside the cluster — no port-forward needed.
set -euo pipefail
source "$(dirname "$0")/../../.env.computed" 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPONENT_DIR="$(dirname "$SCRIPT_DIR")"
NS="${NS_PGVECTOR:-pg-vector}"
JOB_NAME="db-seed-userinfo"

echo "======================================"
echo "Populating userinfo Database (Job: $JOB_NAME)"
echo "======================================"
echo ""

# Idempotency check — skip if data already exists
USER_COUNT=$(oc exec pgvector-0 -n "$NS" -- \
  psql -U "${PG_USERINFO_USER:-user_info}" -d userinfo -tAc \
  "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")

if [[ "$USER_COUNT" -gt 0 ]]; then
    echo "  userinfo database already has $USER_COUNT users. Skipping."
    echo ""
    exit 0
fi

# Clean up previous Job run (Jobs are immutable)
oc delete job "$JOB_NAME" -n "$NS" --ignore-not-found 2>/dev/null
oc delete configmap db-seed-scripts db-seed-data -n "$NS" --ignore-not-found 2>/dev/null
sleep 2

# Create ConfigMaps from the actual source files
echo "  Creating ConfigMap db-seed-scripts ..."
oc create configmap db-seed-scripts -n "$NS" \
    --from-file=populate_postgres_userdata.py="$SCRIPT_DIR/populate_postgres_userdata.py"

echo "  Creating ConfigMap db-seed-data ..."
oc create configmap db-seed-data -n "$NS" \
    --from-file=sample_usage.json="$COMPONENT_DIR/data/sample_usage.json"

# Apply the Job manifest
echo "  Applying $JOB_NAME Job ..."
envsubst < "$SCRIPT_DIR/02-db-seed-job.yaml" | oc apply -f -

# Wait for the Job to complete
echo "  Waiting for Job/$JOB_NAME to complete (timeout 180s) ..."
if oc wait --for=condition=complete "job/$JOB_NAME" -n "$NS" --timeout=180s 2>/dev/null; then
    echo ""
    echo "  Job logs:"
    oc logs "job/$JOB_NAME" -n "$NS" 2>/dev/null | tail -20 | sed 's/^/    /'
    echo ""
    echo "==> User data populated successfully."
else
    echo ""
    echo "  ERROR: Job/$JOB_NAME did not complete within 180s."
    echo "  Job logs:"
    oc logs "job/$JOB_NAME" -n "$NS" 2>/dev/null | tail -30 | sed 's/^/    /'
    exit 1
fi
