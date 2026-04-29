#!/usr/bin/env bash
# Verifies the pgvector instance: extension, databases, roles, and user data.
# Uses oc exec … -c postgres -- psql -U … -d … (always pass -d; default DB is otherwise same as user).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CONFIG="$REPO_ROOT/config/env.properties"
if [[ -f "$CONFIG" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$CONFIG"
    set +a
fi
# shellcheck source=/dev/null
source "$(dirname "$0")/../../.env.computed" 2>/dev/null || true

NS="${NS_PGVECTOR:-agentic-service}"
# Admin connection: must use an existing bootstrap DB (see env.properties POSTGRES_DB / PGVECTOR_DB).
ADMIN_DB="${PGVECTOR_DB:-postgres}"
ADMIN_USER="${PGVECTOR_USER:-appuser}"
POD="pgvector-0"
CONTAINER="postgres"
UI_USER="${PG_USERINFO_USER:-user_info}"
UI_PASS="${PG_USERINFO_PASSWORD:-}"

echo "======================================"
echo "pgvector Verification"
echo "======================================"
echo "  Admin psql: -U ${ADMIN_USER} -d ${ADMIN_DB}"
echo "  userinfo:   -U ${UI_USER} -d userinfo"
echo ""

psql_admin() {
    oc exec "$POD" -n "$NS" -c "$CONTAINER" -- psql -U "$ADMIN_USER" -d "$ADMIN_DB" "$@"
}

psql_userinfo() {
    if [[ -z "$UI_PASS" ]]; then
        echo "  WARNING: PG_USERINFO_PASSWORD unset; userinfo checks may fail."
        oc exec "$POD" -n "$NS" -c "$CONTAINER" -- psql -U "$UI_USER" -d userinfo "$@"
    else
        oc exec "$POD" -n "$NS" -c "$CONTAINER" -- \
            env PGPASSWORD="${UI_PASS}" psql -U "$UI_USER" -d userinfo "$@"
    fi
}

echo "==> Vector extension ..."
if psql_admin -tAc "SELECT 1 FROM pg_extension WHERE extname='vector';" | grep -q 1; then
    echo "  vector extension: OK"
else
    echo "  FAIL: vector extension not found"
    exit 1
fi

echo ""
echo "==> Databases (via admin connection to -d ${ADMIN_DB}) ..."
for db in "${PGVECTOR_DB:-postgres}" userinfo llamastack; do
    if psql_admin -tAc "SELECT 1 FROM pg_database WHERE datname='${db}';" | grep -q 1; then
        echo "  ${db}: OK"
    else
        echo "  WARNING: ${db} not found"
    fi
done

echo ""
echo "==> Tables in userinfo:"
if psql_userinfo -c "\dt+" 2>/dev/null; then
    :
else
    echo "  (no access or no tables — ensure db-init Job completed successfully)"
fi

echo ""
echo "==> Row counts in userinfo:"
psql_userinfo -tAc "
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
