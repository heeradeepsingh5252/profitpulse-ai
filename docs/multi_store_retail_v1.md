# Multi-Store Retail Intelligence v1

## Scope
Reporting-only demo for a clothing retailer with multiple stores. Each store has two analytical workflows:
- Store Data Analyst: sales, revenue, cost of goods sold, gross profit, margin, top products, stock alerts.
- Store Business Analyst: interprets those metrics and provides review recommendations.
- Headquarters Intelligence Agent: ranks stores, consolidates revenue/profit, highlights low stock and flags revenue-threshold expansion candidates.

No purchase orders, stock transfers, pricing changes, or other operational actions are executed.

## Manual CSV uploads

Sales CSV columns (required): `sale_date, sku, product_name, quantity, unit_price, unit_cost`. Optional: `category`.

Inventory CSV columns (required): `snapshot_date, sku, product_name, stock_on_hand, reorder_level, unit_cost`. Optional: `category`.

Templates:
- `examples/retail_sales_template.csv`
- `examples/retail_inventory_template.csv`

Uploads are limited to CSV, 10 MB and 50,000 rows per request. Sales uploads are append-only batches. Inventory rows upsert on organization + store + snapshot date + SKU.

## API
All endpoints require `X-Organization-ID`.

- `GET /api/v1/retail/stores`
- `POST /api/v1/retail/stores`
- `POST /api/v1/retail/stores/{store_id}/upload-sales` (multipart field: `file`)
- `POST /api/v1/retail/stores/{store_id}/upload-inventory` (multipart field: `file`)
- `GET /api/v1/retail/stores/{store_id}/report?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /api/v1/retail/headquarters/report?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `POST /api/v1/retail/headquarters/email` JSON: `{"recipient":"owner@example.com"}`

## Expansion flag
A store is flagged for owner review only when its configured monthly revenue threshold is exceeded in three consecutive calendar months. This is a screening signal, not a recommendation to lease a site. Catchment demand, competition, rent, contribution margin, capacity and cannibalisation must be evaluated separately.

## Metric definition
Revenue = quantity × unit selling price. COGS = quantity × unit cost. Gross profit = revenue − COGS. Gross profit is not net profit. Rent, salaries, utilities, tax, returns and discounts are not included in v1 unless added to the data model.

## Email configuration
Configure `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`, and `REPORT_FROM_EMAIL`. The email endpoint sends on request. A scheduler/cron trigger is a later deployment step.

## Security / deployment
The current public portfolio deployment uses `DEMO_READ_ONLY=true` and the development `X-Organization-ID` header is not authentication. Do not turn off read-only mode on the public deployment to accept real customer uploads. Test write endpoints locally or add authenticated owner/staff access before enabling uploads in a deployed pilot.
