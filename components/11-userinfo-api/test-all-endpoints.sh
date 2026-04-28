#!/bin/bash

# User Info API - Complete Endpoint Validation Script
# Tests all 7 controllers with their endpoints

set -e

API_URL="${1:-http://localhost:8000}"
BASE_URL="${API_URL}/api/v1"

echo "=========================================="
echo "User Info API - Endpoint Validation"
echo "=========================================="
echo "API URL: $API_URL"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_status=$4
    local description=$5

    echo -e "${YELLOW}Testing:${NC} $description"
    echo "  $method $endpoint"

    if [ -z "$data" ]; then
        response=$(curl -sk -X "$method" \
            -w "\n%{http_code}" \
            -H "Content-Type: application/json" \
            "$endpoint" 2>&1)
    else
        response=$(curl -sk -X "$method" \
            -w "\n%{http_code}" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$endpoint" 2>&1)
    fi

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" == "$expected_status" ]; then
        echo -e "  ${GREEN}✓ PASS${NC} (HTTP $http_code)"
        ((pass_count++))
        if [ ! -z "$body" ] && [ "$body" != "null" ]; then
            echo "$body" | python3 -m json.tool 2>/dev/null | head -20 || echo "$body"
        fi
    else
        echo -e "  ${RED}✗ FAIL${NC} (Expected HTTP $expected_status, got $http_code)"
        echo "  Response: $body"
        ((fail_count++))
    fi
    echo ""
}

# ==========================================
# 0. Health Check
# ==========================================
echo "=========================================="
echo "0. HEALTH CHECK"
echo "=========================================="

test_endpoint "GET" "$API_URL/health" "" "200" "Health endpoint"

# ==========================================
# 1. Users API
# ==========================================
echo "=========================================="
echo "1. USERS API"
echo "=========================================="

test_endpoint "GET" "$BASE_URL/users?page=1&page_size=5" "" "200" "List users with pagination"

test_endpoint "GET" "$BASE_URL/users?email=sarah.chen@example.com" "" "200" "Filter users by email"

test_endpoint "GET" "$BASE_URL/users/1" "" "200" "Get user by ID with subscriptions"

test_endpoint "GET" "$BASE_URL/users/99999" "" "404" "Get non-existent user (should fail)"

# Create new user
NEW_USER_DATA='{
  "username": "test_user_'$(date +%s)'",
  "user_name": "Test User",
  "email": "test'$(date +%s)'@example.com",
  "external_id": "test_ext_'$(date +%s)'"
}'

test_endpoint "POST" "$BASE_URL/users" "$NEW_USER_DATA" "201" "Create new user"

# Try to create duplicate user (should fail with 409)
test_endpoint "POST" "$BASE_URL/users" '{
  "username": "sarah_chen",
  "user_name": "Sarah Chen Duplicate",
  "email": "duplicate@example.com"
}' "409" "Create user with duplicate username (should fail)"

# Update user
test_endpoint "PUT" "$BASE_URL/users/1" '{
  "user_name": "Sarah Chen Updated"
}' "200" "Update user (partial update)"

# ==========================================
# 2. Subscriptions API
# ==========================================
echo "=========================================="
echo "2. SUBSCRIPTIONS API"
echo "=========================================="

test_endpoint "GET" "$BASE_URL/subscriptions?page=1&page_size=5" "" "200" "List subscriptions with pagination"

test_endpoint "GET" "$BASE_URL/subscriptions?user_id=1" "" "200" "Filter subscriptions by user_id"

test_endpoint "GET" "$BASE_URL/subscriptions?status=active" "" "200" "Filter subscriptions by status"

test_endpoint "GET" "$BASE_URL/subscriptions/1" "" "200" "Get subscription by ID"

test_endpoint "GET" "$BASE_URL/subscriptions/99999" "" "404" "Get non-existent subscription (should fail)"

# Create new subscription
NEW_SUB_DATA='{
  "user_id": 1,
  "mobile_number": "08'$(date +%s | tail -c 9)'",
  "account_number": "ACC-'$(date +%s)'",
  "status": "active"
}'

test_endpoint "POST" "$BASE_URL/subscriptions" "$NEW_SUB_DATA" "201" "Create new subscription"

# Try to create subscription with non-existent user
test_endpoint "POST" "$BASE_URL/subscriptions" '{
  "user_id": 99999,
  "mobile_number": "0899999999",
  "account_number": "ACC-INVALID",
  "status": "active"
}' "404" "Create subscription with invalid user_id (should fail)"

# Update subscription status
test_endpoint "PATCH" "$BASE_URL/subscriptions/1/status" '{
  "status": "suspended"
}' "200" "Update subscription status to suspended"

test_endpoint "PATCH" "$BASE_URL/subscriptions/1/status" '{
  "status": "active"
}' "200" "Update subscription status back to active"

# ==========================================
# 3. Plans API
# ==========================================
echo "=========================================="
echo "3. PLANS API"
echo "=========================================="

test_endpoint "GET" "$BASE_URL/plans?page=1&page_size=5" "" "200" "List plans with pagination"

test_endpoint "GET" "$BASE_URL/plans/1" "" "200" "Get plan by ID"

test_endpoint "GET" "$BASE_URL/plans/99999" "" "404" "Get non-existent plan (should fail)"

# Create new plan
NEW_PLAN_DATA='{
  "plan_name": "Test Plan '$(date +%s)'",
  "data_limit_gb": 100,
  "voice_limit_minutes": 1000,
  "sms_limit": 500,
  "price": 999.99
}'

test_endpoint "POST" "$BASE_URL/plans" "$NEW_PLAN_DATA" "201" "Create new plan"

# ==========================================
# 4. User Plans API
# ==========================================
echo "=========================================="
echo "4. USER PLANS API"
echo "=========================================="

test_endpoint "GET" "$BASE_URL/subscriptions/1/plans" "" "200" "Get plans for subscription"

test_endpoint "GET" "$BASE_URL/subscriptions/99999/plans" "" "404" "Get plans for non-existent subscription (should fail)"

# Assign plan to subscription
ASSIGN_PLAN_DATA='{
  "plan_id": 1,
  "start_date": "2026-05-01"
}'

test_endpoint "POST" "$BASE_URL/subscriptions/1/plans" "$ASSIGN_PLAN_DATA" "201" "Assign plan to subscription"

# Try to assign non-existent plan
test_endpoint "POST" "$BASE_URL/subscriptions/1/plans" '{
  "plan_id": 99999,
  "start_date": "2026-05-01"
}' "404" "Assign non-existent plan (should fail)"

# ==========================================
# 5. Usage API
# ==========================================
echo "=========================================="
echo "5. USAGE API"
echo "=========================================="

test_endpoint "GET" "$BASE_URL/subscriptions/1/usage" "" "200" "List usage records for subscription"

test_endpoint "GET" "$BASE_URL/subscriptions/1/usage?start_date=2026-04-01&end_date=2026-04-30" "" "200" "List usage with date range filter"

test_endpoint "GET" "$BASE_URL/subscriptions/99999/usage" "" "404" "List usage for non-existent subscription (should fail)"

# Upsert usage record
USAGE_DATA='{
  "usage_date": "2026-04-27",
  "data_used_gb": 5.5,
  "voice_used_minutes": 120,
  "sms_used": 25
}'

test_endpoint "POST" "$BASE_URL/subscriptions/1/usage" "$USAGE_DATA" "201" "Upsert usage record (create)"

# Upsert again (update)
USAGE_UPDATE_DATA='{
  "usage_date": "2026-04-27",
  "data_used_gb": 6.0,
  "voice_used_minutes": 150,
  "sms_used": 30
}'

test_endpoint "POST" "$BASE_URL/subscriptions/1/usage" "$USAGE_UPDATE_DATA" "201" "Upsert usage record (update)"

# Aggregate usage
test_endpoint "GET" "$BASE_URL/subscriptions/1/usage/aggregate?start_date=2026-04-01&end_date=2026-04-30" "" "200" "Aggregate usage over date range"

# Try aggregate without required params (should fail with 422)
test_endpoint "GET" "$BASE_URL/subscriptions/1/usage/aggregate" "" "422" "Aggregate usage without date range (should fail)"

# ==========================================
# 6. Billing API
# ==========================================
echo "=========================================="
echo "6. BILLING API"
echo "=========================================="

test_endpoint "GET" "$BASE_URL/subscriptions/1/bills" "" "200" "List bills for subscription"

test_endpoint "GET" "$BASE_URL/subscriptions/99999/bills" "" "404" "List bills for non-existent subscription (should fail)"

# Create bill
BILL_DATA='{
  "billing_cycle_start": "2026-04-01",
  "billing_cycle_end": "2026-04-30"
}'

test_endpoint "POST" "$BASE_URL/subscriptions/1/bills" "$BILL_DATA" "201" "Create bill for subscription"

# Get specific bill (assuming bill_id=1 exists or was just created)
test_endpoint "GET" "$BASE_URL/subscriptions/1/bills/1" "" "200" "Get specific bill"

test_endpoint "GET" "$BASE_URL/subscriptions/1/bills/99999" "" "404" "Get non-existent bill (should fail)"

# Mark bill as paid
PAYMENT_DATA='{
  "payment_date": "2026-04-15"
}'

test_endpoint "POST" "$BASE_URL/subscriptions/1/bills/1/pay" "$PAYMENT_DATA" "200" "Mark bill as paid"

# ==========================================
# 7. Usage Insights API
# ==========================================
echo "=========================================="
echo "7. USAGE INSIGHTS API"
echo "=========================================="

test_endpoint "GET" "$BASE_URL/subscriptions/1/insights" "" "200" "List usage insights for subscription"

test_endpoint "GET" "$BASE_URL/subscriptions/99999/insights" "" "404" "List insights for non-existent subscription (should fail)"

# Create usage insight
INSIGHT_DATA='{
  "subscription_id": 1,
  "month": "2026-04-01",
  "usage_type": "data",
  "data_usage_percent": 75.5
}'

test_endpoint "POST" "$BASE_URL/subscriptions/1/insights" "$INSIGHT_DATA" "201" "Create usage insight"

# Try creating insight with mismatched subscription_id
INSIGHT_MISMATCH='{
  "subscription_id": 2,
  "month": "2026-04-01",
  "usage_type": "data",
  "data_usage_percent": 50.0
}'

test_endpoint "POST" "$BASE_URL/subscriptions/1/insights" "$INSIGHT_MISMATCH" "400" "Create insight with subscription_id mismatch (should fail)"

# ==========================================
# Summary
# ==========================================
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
total=$((pass_count + fail_count))
echo -e "Total tests: $total"
echo -e "${GREEN}Passed: $pass_count${NC}"
echo -e "${RED}Failed: $fail_count${NC}"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
