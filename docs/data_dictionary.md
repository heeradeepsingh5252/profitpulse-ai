# Day 1 Data Dictionary

## Tenant and ingestion

- `organizations`: business tenant and base currency.
- `app_users`, `organization_members`: local identity/membership foundation; authentication is not implemented on Day 1.
- `data_sources`: where imported data originated.
- `import_jobs`, `import_row_errors`: ingestion audit and row-level validation results.

## Retail and wholesale operations

- `customers`: retail/wholesale/B2B customers and credit limits.
- `suppliers`: supplier directory and payment terms.
- `products`: SKU, category, selling price, current unit cost and reorder level.
- `warehouses`: warehouse/location master.
- `orders`, `order_items`: sales orders; item rows keep `unit_cost_snapshot` so historical gross margin does not change when current product costs change.
- `purchase_orders`, `purchase_order_items`: supplier purchases and received quantities.
- `payments`: inbound customer receipts and outbound supplier settlements.
- `inventory_movements`: quantity deltas with purchase/sale/return/adjustment type.
- `inventory_snapshots`: on-hand quantity snapshots by product and warehouse.
- `expenses`: operational expense detail; the GL journal is the financial reporting source of truth.

## General ledger

- `gl_accounts`: organization-specific chart of accounts and reporting category.
- `journal_entries`: accounting event header; only `posted` entries are included in financial summaries.
- `journal_lines`: debit/credit legs. A row must have exactly one positive side. The posting function verifies total debits equal total credits.
- `fixed_assets`, `loan_accounts`, `budgets`: additional source data for later balance-sheet, debt, depreciation and planning features.

## Day 1 seed chart of accounts

| Code | Account | Reporting category |
|---|---|---|
| 1000 | Cash and Cash Equivalents | cash |
| 1100 | Accounts Receivable | receivable |
| 1200 | Inventory | inventory |
| 1500 | Property, Plant and Equipment | fixed_asset |
| 1590 | Accumulated Depreciation | accumulated_depreciation |
| 2000 | Accounts Payable | payable |
| 2100 | Bank Loan Payable | debt |
| 2200 | Income Tax Payable | tax_payable |
| 3000 | Owner Capital | equity |
| 4000 | Sales Revenue | revenue |
| 4050 | Sales Returns and Allowances | contra_revenue |
| 5000 | Cost of Goods Sold | cogs |
| 6000–6400 | Operating expense accounts | operating_expense |
| 7000 | Depreciation Expense | depreciation |
| 7100 | Amortisation Expense | amortization |
| 7200 | Interest Expense | interest_expense |
| 7300 | Income Tax Expense | income_tax |

All seed rows belong to the sample tenant UUID `11111111-1111-4111-8111-111111111111` and are fictional.
