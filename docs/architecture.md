# ProfitPulse AI Architecture — Day 1 and Day 2

## Request path

1. A user sends a tenant-scoped request to FastAPI.
2. The API opens a PostgreSQL transaction.
3. The API sets `app.current_organization_id` transaction-locally using `set_config(..., true)`.
4. PostgreSQL row-level security filters tenant-owned rows.
5. Application queries use parameter binding.

## Double-entry accounting

`gl_accounts` is the chart of accounts. A `journal_entry` contains two or more `journal_lines`. Each line has either a positive debit or a positive credit, never both. The `create_balanced_journal_entry` function inserts a draft, validates account codes, sums debit and credit totals, rejects an imbalance and posts the entry. Posted journal lines are immutable through ordinary DML.

## Financial intelligence calculations

The financial service aggregates posted journal lines by `financial_category` and uses Python `Decimal` arithmetic.

- Net revenue = gross sales - sales returns.
- Gross profit = net revenue - COGS.
- EBITDA = gross profit - operating expenses (excluding depreciation, amortisation, interest and income tax).
- EBIT = EBITDA - depreciation - amortisation.
- PBT = EBIT - interest expense (non-operating income is not yet modelled in this starter).
- PAT = PBT - income tax expense.

The balance sheet uses normal debit/credit balances and includes current fiscal-year earnings in equity because the demo ledger does not post year-end closing entries. It exposes an accounting-equation check. Debt maturity is not split into current/non-current portions, so standard current and quick ratios are not returned. See `docs/day2_financial_engine.md` for the exact basis and limitations of each endpoint.

## Day 2 analytics endpoints

- Period P&L summary.
- Balance sheet as of a specified date.
- Financial ratios using average asset/equity balances where defined.
- Monthly P&L trends.
- Exact-period budget variance.
- Product and regional profitability from delivered order item lines.
- Inventory health based on latest available snapshots.

## Multi-tenant security boundary

The schema enables and forces RLS. FastAPI sets tenant context from `X-Organization-ID` strictly for local development. This is not authentication. Before any public/customer deployment, implement verified identity (OIDC/JWT), membership authorization, derive organization ID from the authenticated principal, keep the app DB role non-owner/non-superuser, review all queries, and test cross-tenant isolation.

## Current limits

- CSV import supports customers and products only.
- The demo API accepts an organization UUID header and has no login.
- The data is synthetic management-reporting data, not audited statements.
- Non-operating income, year-end closing entries and full cash-flow classification are not yet included.
- Debt is not split into current and non-current portions.
- The LLM agent, RAG, MCP, forecasting and custom frontend are later build phases.
