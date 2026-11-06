#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
ORG_ID="${ORG_ID:-11111111-1111-4111-8111-111111111111}"
QUESTION="${QUESTION:-Why is EBITDA negative for August through October 2026? Compare monthly performance, product profitability and operating expenses.}"

PAYLOAD="$(python3 -c 'import json,sys; print(json.dumps({"question": sys.argv[1], "max_tool_rounds": 6}))' "$QUESTION")"
curl -sS -X POST "$BASE_URL/api/v1/agent/ask" \
  -H 'Content-Type: application/json' \
  -H "X-Organization-ID: $ORG_ID" \
  -d "$PAYLOAD" \
  | python3 -m json.tool
