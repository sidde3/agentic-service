#!/bin/bash
# Multi-turn chat test via the Router service.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../scripts/utils.sh"
load_config

SESSION="multiturn-$(date +%s)"

echo ""
echo "=== Multi-Turn Chat Test ==="
echo "Router: $ROUTER_ROUTE_URL"
echo "User:   $USER_EMAIL"
echo "Session: $SESSION"
echo ""

USER_EMAIL="${1:-jessica.thompson@example.com}"

chat() {
    local turn="$1" message="$2" intent="${3:-}"
    echo "--- Turn $turn ---"
    local body="{\"user_email\":\"$USER_EMAIL\",\"message\":\"$message\",\"session_id\":\"$SESSION\""
    if [[ -n "$intent" ]]; then
        body="$body,\"predefined_intent\":\"$intent\""
    fi
    body="$body}"

    curl -sk -X POST "$ROUTER_ROUTE_URL/chat" \
        -H "Content-Type: application/json" \
        -d "$body" | python3 -m json.tool
    echo ""
}

chat 1 "Check my current data usage" "MOBILE_USAGE_CHECK_DATA_CURRENT"
chat 2 "My usage is too high. Compare plans and recommend a better one." "MOBILE_USAGE_COMPARE_DATA_PLAN"
chat 3 "Tell me more about the Premium 50GB plan" "MOBILE_USAGE_COMPARE_DATA_PLAN"

echo "=== Test Complete ==="
