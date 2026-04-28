#!/bin/bash
# Creates databases, roles, and enables the vector extension via a Kubernetes Job.
set -euo pipefail
source "$(dirname "$0")/../../.env.computed" 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS="${NS_PGVECTOR:-pg-vector}"
JOB_NAME="db-init"

echo "======================================"
echo "Database Initialization (Job: $JOB_NAME)"
echo "======================================"
echo ""

# Delete previous Job run if it exists (Jobs are immutable)
oc delete job "$JOB_NAME" -n "$NS" --ignore-not-found 2>/dev/null
oc delete configmap db-init-sql -n "$NS" --ignore-not-found 2>/dev/null
sleep 2

# Apply the Job manifest (envsubst fills in variable references)
echo "  Applying $JOB_NAME Job ..."
envsubst < "$SCRIPT_DIR/01-db-init-job.yaml" | oc apply -f -

# Wait for the Job to complete
echo "  Waiting for Job/$JOB_NAME to complete (timeout 120s) ..."
if oc wait --for=condition=complete "job/$JOB_NAME" -n "$NS" --timeout=120s 2>/dev/null; then
    echo ""
    echo "  Job logs:"
    oc logs "job/$JOB_NAME" -n "$NS" 2>/dev/null | sed 's/^/    /'
    echo ""
    echo "==> Database initialization complete."
else
    echo ""
    echo "  ERROR: Job/$JOB_NAME did not complete within 120s."
    echo "  Job logs:"
    oc logs "job/$JOB_NAME" -n "$NS" 2>/dev/null | sed 's/^/    /'
    exit 1
fi
