#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${API_BASE_URL:-http://localhost:8000}}"
HEALTH_URL="${BASE_URL%/}/api/health"

status="$(
  curl -fsS "$HEALTH_URL" \
    | python3 -c 'import json, sys; print(json.load(sys.stdin).get("status", ""))'
)"

if [[ "$status" != "ok" ]]; then
  echo "health check failed: status=${status:-missing}" >&2
  exit 1
fi

echo "health check passed: $HEALTH_URL status=$status"
