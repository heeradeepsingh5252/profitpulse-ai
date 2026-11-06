# ProfitPulse AI — Supply Chain Intelligence v1

## Objective

Connect the physical flow of goods to the existing procurement, inventory and financial data in ProfitPulse:

**Supplier origin → purchase order → inbound shipment → tracking milestones → warehouse receipt and inspection → inventory movement.**

This is a local development/demo release using synthetic supplier and shipment examples. It is not connected to live carriers, GPS, customs, EDI or supplier email systems.

## Capabilities in v1

### Supplier origin network
- Keep one or more origin sites for each supplier without overwriting the supplier's master city.
- Store site type (factory, warehouse, distribution centre, port or other), city, state, country/code, port, default lead-time days and preferred transport mode.
- Optionally designate one primary origin per supplier.

### Procurement workflow
- Create draft purchase orders from active catalog products.
- Validate supplier/product ownership against the current organization.
- Mark a draft PO as sent, which changes its workflow status and creates an audit event.
- **Important:** marking a PO as sent does not email the supplier or transmit an EDI message.

### Inbound shipments
- Link a shipment to one supplier and one or more of that supplier's sent/partially received POs.
- Record origin site, destination warehouse, transport mode, carrier/reference, Incoterm, planned departure, promised arrival and current ETA.
- Prevent shipment quantities from exceeding outstanding PO quantities already assigned to other non-cancelled shipments.
- Store shipment line quantities and goods value from PO unit costs.

### Tracking timeline and exceptions
- Record manually entered milestones such as pickup, departure, in transit, ports, customs, out-for-delivery, warehouse arrival, delay and exception.
- Preserve event time, reported location, notes and source (`manual`, with future enum values reserved for integrations).
- Flag delayed/exception statuses, overdue current ETAs and in-transit tracking records without a new event for more than 72 hours. Shipments already at the warehouse are excluded from stale in-transit tracking alerts.
- Calculate actual transit days only when both actual departure and actual arrival are recorded.
- A goods receipt can be posted only after an `arrived_warehouse` milestone has placed the shipment in `arrived_at_warehouse`. Physical arrival is not the same as inspected/accepted stock.

### Goods receipt and inventory integration
- Record physically received, accepted and rejected quantities separately.
- Require accepted + rejected = physically received.
- Accepted quantities update the existing purchase-order line received quantity and create `purchase` inventory movements.
- Rejected quantities are recorded in the receipt but do not count as fulfilled PO quantity and are not added to available inventory.
- Inventory Health incorporates movements posted after the latest stock snapshot. A receipt dated on/before the latest snapshot for the target product/warehouse is rejected; a corrected/new stock snapshot is required instead.

### Shipment charges
- Record freight, insurance, customs duty/brokerage, port handling, inland transport and other charges in the shipment's currency.
- Charges are displayed in shipment records and timeline.
- **Not yet implemented:** currency conversion, automatic landed-cost allocation to product inventory valuation, or automatic general-ledger journal posting.

### Supplier scorecards
- Purchase-order on-time percentage uses completed POs with an expected date.
- OTIF uses completed POs with an expected date and item quantities accepted at least equal to quantities ordered.
- Fill rate = accepted PO quantity / quantity ordered. Rejected units do not count as fulfilled.
- Procurement lead time = PO order date to recorded received date.
- Transit time = actual departure to actual arrival.
- Rejected quantity percentage = rejected / physically received quantity.
- Metrics can be `null` where there is insufficient completed data. Small samples are descriptive and should not be interpreted as statistically reliable supplier ratings.

## API routes

All routes are prefixed `/api/v1/supply-chain` and require `X-Organization-ID` in this local demo.

| Method | Route | Purpose |
|---|---|---|
| GET | `/overview` | Open POs, active/delayed shipments, stale tracking, average transit and open goods value |
| GET | `/catalog` | Tenant-scoped suppliers, products, warehouses and currency for forms |
| GET | `/suppliers` | Supplier origin sites |
| POST | `/suppliers/{supplier_id}/sites` | Add supplier origin site |
| GET | `/purchase-orders` | List purchase orders |
| POST | `/purchase-orders` | Create draft purchase order |
| POST | `/purchase-orders/{purchase_order_id}/send` | Mark draft PO as sent |
| GET | `/shipments` | List shipments, latest milestone, value, charges and ETA |
| POST | `/shipments` | Create inbound shipment against outstanding PO quantities |
| GET | `/shipments/{shipment_id}/timeline` | Events, lines and shipment charges |
| POST | `/shipments/{shipment_id}/events` | Record tracking milestone / revised ETA |
| POST | `/shipments/{shipment_id}/charges` | Record shipment cost |
| POST | `/shipments/{shipment_id}/receipts` | Record goods receipt and accepted inventory quantity |
| GET | `/supplier-scorecards` | Supplier performance metrics |
| GET | `/exceptions` | Delays, past-due ETAs and stale-tracking exceptions |

## AI and MCP integration

The LangGraph Business Analyst receives read-only organization-bound tools:
- `get_supply_chain_overview`
- `get_inbound_shipments`
- `get_shipment_timeline`
- `get_supplier_scorecards`
- `get_supply_chain_exceptions`

The MCP service exposes the corresponding read-only supply-chain resources/tools. Write operations remain explicit API/UI workflows, not autonomous LLM tool calls.

The system prompt tells the agent to distinguish manual tracking evidence from live telemetry, treat a delay as an alert rather than proof of supplier fault, and distinguish warehouse arrival from accepted inventory.

## Data model

Migration `database/migrations/20261106_supply_chain_v1.sql` adds:
- `sc_supplier_sites`
- `sc_inbound_shipments`
- `sc_shipment_purchase_orders`
- `sc_shipment_items`
- `sc_shipment_events`
- `sc_shipment_costs`
- `sc_goods_receipts`
- `sc_goods_receipt_items`

All new tables have `organization_id`, tenant RLS policies and organization-aware foreign keys. Existing supplier, purchase-order, product, warehouse and inventory tables are extended through references; existing financial tables are not dropped or rebuilt.

## Demo seed data

`database/seeds/20261106_supply_chain_demo_seed.sql` is optional and intended only for the seeded demo organization `11111111-1111-4111-8111-111111111111`. It adds synthetic origin sites, shipment history, one in-transit example and one delayed example. Carrier names, tracking numbers and events are fictional. The seed uses conflict handling so it can be re-run without duplicating rows.

## Known limitations and production work

1. Tracking events are manually entered. No carrier APIs, GPS, webhook, EDI, customs or port integrations are active.
2. POs are marked sent in the application; no supplier email or ERP transmission occurs.
3. Freight/handling charges are stored separately; no landed-cost allocation, FX conversion or GL posting is active.
4. There is no route map/geocoding or real-time location estimation.
5. The `X-Organization-ID` header and MCP fixed demo organization are development-only tenant selectors, not authentication. Production requires identity, organization membership authorization and scoped service credentials.
6. Add operational monitoring, backup/restore, idempotency keys for external imports, carrier reconciliation and load tests before production use.
7. Supplier KPIs should show sample sizes and be reviewed with business context; the demo seed is too small for meaningful vendor benchmarking.

## FDE discovery questions for a real deployment

Before configuring this module for a real customer, establish:
- Supplier master source of truth and whether suppliers have multiple factories/dispatch sites.
- Which ERP/procurement system owns PO creation and acknowledgement.
- Which carriers, freight forwarders, ports and customs brokers provide tracking data, and through what API/EDI/file format.
- What counts as promised delivery: PO expected date, supplier-confirmed date or carrier ETA.
- What event statuses and escalation SLAs the operations team uses.
- Whether goods receipt is quantity-only or includes QC attributes, lot/batch, serial, expiry and damage evidence.
- Which Incoterms and currencies are used and who owns customs/freight charges.
- Whether landed costs should be allocated by units, weight, volume, value or a customer-specific policy.
- Which warehouse/WMS owns stock balances and how receipts/returns/transfer corrections are reconciled.
