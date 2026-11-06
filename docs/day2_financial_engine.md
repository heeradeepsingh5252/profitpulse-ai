# ProfitPulse AI — Day 2 Financial Intelligence Engine

Day 2 extends the Day 1 PostgreSQL ledger and FastAPI foundation. It does not change the database schema or require a volume reset.

## New API endpoints

All organization-scoped endpoints require the development-only `X-Organization-ID` header. The demo organization ID is:

```text
11111111-1111-4111-8111-111111111111
```

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/financial/summary` | Period P&L, including revenue, gross profit, EBITDA, EBIT, PBT and PAT |
| GET | `/api/v1/financial/balance-sheet` | Ledger balances as of a date, including the accounting-equation check |
| GET | `/api/v1/financial/ratios` | Margin, ROA, ROE, asset turnover, debt/equity and interest coverage |
| GET | `/api/v1/financial/monthly-trend` | Month-wise P&L metrics |
| GET | `/api/v1/financial/budget-variance` | Actual vs budget for configured metrics and exact period dates |
| GET | `/api/v1/analytics/product-performance` | Delivered-order sales, COGS and gross profit by product |
| GET | `/api/v1/analytics/regional-performance` | Delivered-order sales, COGS and gross profit by region |
| GET | `/api/v1/analytics/inventory-health` | Latest stock snapshot, inventory value and reorder flag |

## Example requests

```bash
ORG_ID=11111111-1111-4111-8111-111111111111

curl -H "X-Organization-ID: $ORG_ID" \
  "http://localhost:8000/api/v1/financial/summary?start_date=2026-08-01&end_date=2026-10-31"

curl -H "X-Organization-ID: $ORG_ID" \
  "http://localhost:8000/api/v1/financial/balance-sheet?as_of_date=2026-10-31"

curl -H "X-Organization-ID: $ORG_ID" \
  "http://localhost:8000/api/v1/financial/ratios?start_date=2026-08-01&end_date=2026-10-31"

curl -H "X-Organization-ID: $ORG_ID" \
  "http://localhost:8000/api/v1/financial/monthly-trend?start_date=2026-08-01&end_date=2026-10-31"

curl -H "X-Organization-ID: $ORG_ID" \
  "http://localhost:8000/api/v1/financial/budget-variance?period_start=2026-10-01&period_end=2026-10-31"

curl -H "X-Organization-ID: $ORG_ID" \
  "http://localhost:8000/api/v1/analytics/product-performance?start_date=2026-08-01&end_date=2026-10-31&limit=10"

curl -H "X-Organization-ID: $ORG_ID" \
  "http://localhost:8000/api/v1/analytics/regional-performance?start_date=2026-08-01&end_date=2026-10-31"

curl -H "X-Organization-ID: $ORG_ID" \
  "http://localhost:8000/api/v1/analytics/inventory-health?as_of_date=2026-11-01"
```

## Metric definitions and limitations

### Profit and loss

- Net revenue = gross sales less sales returns and allowances.
- Gross profit = net revenue less cost of goods sold.
- EBITDA = gross profit less operating expenses classified separately from depreciation, amortisation, interest and income tax.
- EBIT = EBITDA less depreciation and amortisation.
- PBT = EBIT less interest expense. Non-operating income is not yet modelled in this starter.
- PAT = PBT less income tax expense.

This is a management-reporting calculation over posted ledger entries. EBITDA adjustments, non-operating income, extraordinary items and statutory accounting treatments may differ by company and accounting policy.

### Balance sheet

- Balance sheet account balances are calculated using each account's normal debit or credit balance.
- Current fiscal-year PAT is added to contributed equity because the demo ledger does not post year-end closing entries to retained earnings.
- The response includes `balance_check_difference` and `is_balanced` so users can identify a ledger that does not reconcile.
- Debt is not classified into current and non-current portions in Day 1. Therefore the API intentionally does not calculate a standard current ratio or quick ratio.
- `operating_working_capital_proxy_excluding_cash_and_borrowings` is explicitly a proxy, not a fully classified net working capital figure.

### Ratios

- ROA = period PAT / average opening and closing total assets.
- ROE = period PAT / average opening and closing equity including current fiscal-year earnings.
- Asset turnover = period net revenue / average total assets.
- Debt/equity = closing ledger debt / closing equity including current fiscal-year earnings.
- Interest coverage = period EBIT / period interest expense.

If a denominator is zero, the API returns `null` rather than infinity. Ratio interpretation depends on period length, accounting policy, seasonality and data completeness.

### Product and regional performance

- Only delivered orders are included.
- Item `line_total` is treated as net sales; order-level tax and shipping are excluded.
- COGS is calculated from item quantity multiplied by the unit-cost snapshot stored at sale time.
- This operational view may not exactly equal ledger net revenue where ledger postings include shipping, tax, accruals or other adjustments.

### Budget variance

- Budgets are matched on exact `period_start` and `period_end` values.
- Revenue/profit metrics are treated as higher-is-better.
- Expense/COGS metrics are treated as lower-is-better.
- Unknown budget metric codes are returned without an actual value until an actual calculation is configured.

### Inventory health

- The API uses the most recent inventory snapshot on or before the requested date for each product/warehouse.
- The reorder alert compares the summed on-hand quantity across warehouses with the product-level reorder level.
- The result is only as current as the underlying snapshots.

## Local upgrade from Day 1

This Day 2 update does not require a database schema migration or resetting the PostgreSQL volume. It only updates backend Python code, tests and documentation.

From the folder that contains `profitpulse_day1_complete`:

```bash
unzip -o ~/Downloads/ProfitPulse_AI_Day2_Update.zip
cd profitpulse_day1_complete
docker compose up --build -d api
docker compose ps
```

Then run:

```bash
docker compose exec api pytest -q
```

The API docs are available at http://localhost:8000/docs.

## Security boundary

The `X-Organization-ID` header remains a local demo selector only. It is not authentication. Before any public customer pilot, derive organization identity from a verified session, verify membership and roles, test RLS with the real application role, restrict database permissions, and add TLS, secrets management, backups, rate limits, audit monitoring and a security review.
