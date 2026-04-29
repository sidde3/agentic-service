#!/usr/bin/env bash
# Expand ${VAR} from the environment and oc apply one YAML file or every *.yaml in a directory.
# Usage:  scripts/apply-manifest.sh path/to/file.yaml
#         scripts/apply-manifest.sh path/to/manifests/
set -euo pipefail

_target="${1:?usage: apply-manifest.sh <file.yaml|directory>}"

_expand() {
  python3 -c '
import os, re, sys
text = sys.stdin.read()
out = re.sub(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
    lambda m: os.environ.get(m.group(1), ""),
    text,
)
sys.stdout.write(out)
'
}

_apply_file() {
  local f="$1"
  echo "  Applying $(basename "$f") ..."
  _expand < "$f" | oc apply -f -
}

if [[ -f "$_target" ]]; then
  _apply_file "$_target"
elif [[ -d "$_target" ]]; then
  shopt -s nullglob
  for f in "$_target"/*.yaml; do
    _apply_file "$f"
  done
else
  echo "ERROR: not a file or directory: $_target" >&2
  exit 1
fi
