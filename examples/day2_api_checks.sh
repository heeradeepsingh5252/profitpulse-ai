#!/usr/bin/env bash
set -euo pipefail

ORG_ID="${ORG_ID:-11111111-1111-4111-8111-111111111111}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
HEADER="X-Organization-ID: ${ORG_ID}"

curl -fsS -H "$HEADER" "$BASE_URL/api/v1/financial/summary?start_date=2026-08-01&end_date=2026-10-31"
echo
curl -fsS -H "$HEADER" "$BASE_URL/api/v1/financial/balance-sheet?as_of_date=2026-10-31"
echo
curl -fsS -H "$HEADER" "$BASE_URL/api/v1/financial/ratios?start_date=2026-08-01&end_date=2026-10-31"
echo
curl -fsS -H "$HEADER" "$BASE_URL/api/v1/financial/monthly-trend?start_date=2026-08-01&end_date=2026-10-31"
echo
curl -fsS -H "$HEADER" "$BASE_URL/api/v1/financial/budget-variance?period_start=2026-10-01&period_end=2026-10-31"
echo
curl -fsS -H "$HEADER" "$BASE_URL/api/v1/analytics/product-performance?start_date=2026-08-01&end_date=2026-10-31&limit=10"
echo
curl -fsS -H "$HEADER" "$BASE_URL/api/v1/analytics/regional-performance?start_date=2026-08-01&end_date=2026-10-31"
echo
curl -fsS -H "$HEADER" "$BASE_URL/api/v1/analytics/inventory-health?as_of_date=2026-11-01"
echo
