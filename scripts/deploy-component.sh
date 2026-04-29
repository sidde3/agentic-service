#!/bin/bash
# Deploy a single component by name or number prefix.
# Usage: bash scripts/deploy-component.sh 08-agent
#        bash scripts/deploy-component.sh 02-pgvector
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"
load_config

COMPONENT_PATTERN="${1:?Usage: deploy-component.sh <component-name>}"
COMPONENTS_DIR="$REPO_ROOT/components"

# Find matching component directory
COMPONENT_DIR=""
for dir in "$COMPONENTS_DIR"/*"$COMPONENT_PATTERN"*/; do
    if [[ -d "$dir" ]]; then
        COMPONENT_DIR="$dir"
        break
    fi
done

if [[ -z "$COMPONENT_DIR" ]]; then
    echo "ERROR: No component matching '$COMPONENT_PATTERN' found in $COMPONENTS_DIR/"
    echo "Available components:"
    ls -1d "$COMPONENTS_DIR"/[0-9][0-9]-*/ 2>/dev/null | while read -r d; do basename "$d"; done
    exit 1
fi

COMPONENT_NAME=$(basename "$COMPONENT_DIR")
section "Deploying $COMPONENT_NAME"

apply_manifests "$COMPONENT_DIR/manifests"

echo ""
echo "  Manifests applied. Run post-deploy scripts manually if needed:"
echo "    ls $COMPONENT_DIR/post-deploy/"
echo ""
