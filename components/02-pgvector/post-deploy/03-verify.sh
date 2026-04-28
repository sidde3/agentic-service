#!/bin/bash
# Verifies the pgvector instance: extension, databases, roles, and user data.
set -euo pipefail
source "$(dirname "$0")/../../.env.computed" 2>/dev/null || true

NS="${NS_PGVECTOR:-pg-vector}"
DB="${PGVECTOR_DB:-pgvector}"
USER="${PGVECTOR_USER:-appuser}"
POD="pgvector-0"

echo "======================================"
echo "pgvector Verification"
echo "======================================"
echo ""

echo "==> Vector extension ..."
if oc exec "$POD" -n "$NS" -- \
  psql -U "$USER" -d "$DB" -tAc "SELECT 1 FROM pg_extension WHERE extname='vector';" | grep -q 1; then
  echo "  vector extension: OK"
else
  echo "  FAIL: vector extension not found"
  exit 1
fi

echo ""
echo "==> Databases ..."
for db in pgvector userinfo llamastack; do
  if oc exec "$POD" -n "$NS" -- \
    psql -U "$USER" -tAc "SELECT 1 FROM pg_database WHERE datname='$db';" | grep -q 1; then
    echo "  $db: OK"
  else
    echo "  WARNING: $db not found"
  fi
done

echo ""
echo "==> Tables in userinfo:"
oc exec "$POD" -n "$NS" -- psql -U "$USER" -d userinfo -c "\dt+" 2>/dev/null || echo "  (no tables — run 02-populate-userdata.sh)"

echo ""
echo "==> Row counts in userinfo:"
oc exec "$POD" -n "$NS" -- psql -U "$USER" -d userinfo -tAc "
  SELECT 'users: '          || COUNT(*) FROM users;
  SELECT 'subscriptions: '  || COUNT(*) FROM subscriptions;
  SELECT 'plans: '          || COUNT(*) FROM plans;
  SELECT 'user_plans: '     || COUNT(*) FROM user_plans;
  SELECT 'usage_records: '  || COUNT(*) FROM usage_records;
  SELECT 'billing: '        || COUNT(*) FROM billing;
  SELECT 'usage_insights: ' || COUNT(*) FROM usage_insights;
  SELECT 'chat_sessions: '  || COUNT(*) FROM chat_sessions;
" 2>/dev/null | while read -r line; do echo "  $line"; done || echo "  (tables not populated yet)"

echo ""
echo "==> Verification complete."
