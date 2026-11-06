# ProfitPulse AI API Reference

Version: 1.0.0  
Environment: Local synthetic-data demonstration

## Base URLs

- Frontend: http://localhost:3000
- FastAPI: http://localhost:8000
- MCP Streamable HTTP: http://localhost:8001/mcp
- OpenAPI schema: http://localhost:8000/openapi.json
- Interactive API docs: http://localhost:8000/docs

## Tenant context

Business and knowledge routes require the `X-Organization-ID` header.

Local demo organization:

`11111111-1111-4111-8111-111111111111`

This caller-supplied header is a development tenant selector, not authentication or authorization. Do not use it as a production security boundary.

Example:

```bash
curl -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' \
  http://localhost:8000/api/v1/dashboard/summary
```

## Health

- `GET /health`
- `GET /health/db`

## Dashboard and analytics

- `GET /api/v1/dashboard/summary`
- `GET /api/v1/analytics/inventory-health`
- `GET /api/v1/analytics/product-performance`
- `GET /api/v1/analytics/regional-performance`

## Financial intelligence

- `GET /api/v1/financial/summary`
- `GET /api/v1/financial/monthly-trend`
- `GET /api/v1/financial/ratios`
- `GET /api/v1/financial/budget-variance`
- `GET /api/v1/financial/balance-sheet`

Monthly trend example:

```bash
curl -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' \
  'http://localhost:8000/api/v1/financial/monthly-trend?start_date=2026-08-01&end_date=2026-10-31'
```

## AI agent

- `POST /api/v1/agent/ask`
- `GET /api/v1/agent/capabilities`

The agent uses a Groq-backed LangGraph workflow and predefined tools. Model access depends on configured provider credentials, network access and account limits.

## Knowledge and RAG

- `GET /api/v1/knowledge/documents`
- `GET /api/v1/knowledge/documents/{document_id}`
- `POST /api/v1/knowledge/search`

The local knowledge store uses ChromaDB and organization metadata filtering. Retrieved chunks can include filename and page citations.

## Imports

- `/api/v1/imports/{entity}`
- `/api/v1/imports/{job_id}`

## Supply chain

- `GET /api/v1/supply-chain/overview`
- `GET /api/v1/supply-chain/catalog`
- `GET /api/v1/supply-chain/suppliers`
- `GET /api/v1/supply-chain/suppliers/{supplier_id}/sites`
- `GET /api/v1/supply-chain/purchase-orders`
- `POST /api/v1/supply-chain/purchase-orders/{purchase_order_id}/send`
- `GET /api/v1/supply-chain/shipments`
- `GET /api/v1/supply-chain/shipments/{shipment_id}/timeline`
- `POST /api/v1/supply-chain/shipments/{shipment_id}/events`
- `POST /api/v1/supply-chain/shipments/{shipment_id}/charges`
- `POST /api/v1/supply-chain/shipments/{shipment_id}/receipts`
- `GET /api/v1/supply-chain/exceptions`
- `GET /api/v1/supply-chain/supplier-scorecards`

Shipment tracking events in this release are manually recorded. Live carrier, GPS, EDI and customs integrations are not configured.

## MCP tools

Endpoint: `http://localhost:8001/mcp`

The MCP server advertises these seven tools:

1. `search_knowledge_base`
2. `get_monthly_financial_trend`
3. `get_supply_chain_overview`
4. `get_inbound_shipments`
5. `get_shipment_timeline`
6. `get_supplier_scorecards`
7. `get_supply_chain_exceptions`

The MCP server is pinned to the local demo organization. It is not configured for production authentication.

For exact request and response schemas, use the running OpenAPI document as the source of truth.
