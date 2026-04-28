#!/bin/bash
# Runs all test scripts sequentially.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo "  Running all tests"
echo "============================================================"

echo ""
echo ">>> Health checks"
bash "$SCRIPT_DIR/test-health.sh"

echo ""
echo ">>> Multi-turn chat"
bash "$SCRIPT_DIR/test-multiturn.sh"

echo ""
echo "All tests complete."
