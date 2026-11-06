# Supply Chain API — local test guide

Base URL: `http://localhost:8000`

Demo organization: `11111111-1111-4111-8111-111111111111`

All examples use synthetic demo data. These APIs require the development-only `X-Organization-ID` header.

## 1. Overview

```bash
curl -s http://localhost:8000/api/v1/supply-chain/overview \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool
```

## 2. Catalog and supplier origins

```bash
curl -s http://localhost:8000/api/v1/supply-chain/catalog \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool

curl -s http://localhost:8000/api/v1/supply-chain/suppliers \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool
```

## 3. Procurement pipeline and inbound visibility

```bash
curl -s 'http://localhost:8000/api/v1/supply-chain/purchase-orders?limit=100' \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool

curl -s 'http://localhost:8000/api/v1/supply-chain/shipments?limit=100' \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool
```

## 4. Exceptions and supplier scorecards

```bash
curl -s http://localhost:8000/api/v1/supply-chain/exceptions \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool

curl -s http://localhost:8000/api/v1/supply-chain/supplier-scorecards \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool
```

## 5. Agent prompt

In the dashboard AI Analyst, ask:

> Which inbound shipments are active? For each, show supplier, origin, destination, latest recorded location, current ETA and status. Identify overdue or stale shipments. Distinguish manually entered events from live tracking, and do not infer the reason for a delay without evidence.

Expected tools include `get_supply_chain_overview`, `get_inbound_shipments` and `get_supply_chain_exceptions`. If asking about a specific shipment's history, use `get_shipment_timeline` after identifying its shipment UUID.

## 6. Operational caveats

- Demo shipment/carrier/tracking records are synthetic.
- Shipment status `arrived_at_warehouse` means physical arrival was recorded; it does not mean accepted stock has been posted.
- Only accepted quantities in a goods receipt create inventory movements. Rejected quantities remain recorded as rejected and do not count as fulfilled PO quantity.
- Shipment costs are not automatically allocated into landed cost or posted to the general ledger.
- This development tenant header is not a production security boundary.
