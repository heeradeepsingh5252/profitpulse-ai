# Apply Supply Chain Intelligence v1

This is an additive migration for the existing ProfitPulse Day 1–5 project. It does not reset PostgreSQL or ChromaDB. Keep `.env` unchanged and do not run `docker compose down -v`.

## 1. Extract the patch

```bash
cd ~/Projects/profitpulse_day1_complete
unzip -o ~/Downloads/ProfitPulse_AI_Supply_Chain_Phase1_Patch.zip -d ~/Projects/profitpulse_day1_complete
```

## 2. Apply the database migration as the PostgreSQL admin role

Run from the project root:

```bash
docker compose exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < database/migrations/20261106_supply_chain_v1.sql
```

Expected ending: `COMMIT`.

## 3. Load synthetic demo supply-chain rows (recommended for the walkthrough)

```bash
docker compose exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < database/seeds/20261106_supply_chain_demo_seed.sql
```

This seed is for the local demo organization only. It inserts fictional carrier names, tracking numbers, route events, an in-transit shipment and a delayed shipment. Do not load the demo seed into a real customer database.

## 4. Build and start API, MCP and frontend

```bash
docker compose build --no-cache api mcp frontend
docker compose up -d --force-recreate api mcp frontend
docker compose ps
```

Do not rebuild or recreate the database service unless you have a separate reason; it is not required for this migration.

## 5. Run tests

```bash
docker compose exec api pytest -q
```

The existing backend suite had 53 tests before Supply Chain v1. This patch adds 10 focused supply-chain calculation/serialization tests; the target full suite is 63 passing tests. The actual result from your Docker environment is authoritative.

## 6. Verify API and frontend

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/v1/supply-chain/overview -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool
curl -s http://localhost:8000/api/v1/supply-chain/shipments -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' | python3 -m json.tool
curl -I http://localhost:3000
```

Open `http://localhost:3000` and choose **Supply chain** from the sidebar.

## 7. First AI test

Ask the AI Analyst:

> Which inbound shipments are active? Tell me where the goods originate, their destination, last recorded location and current ETA. Identify any delayed or stale shipment. State clearly that tracking events are manual in this local demo.

Look for `get_supply_chain_overview`, `get_inbound_shipments` and `get_supply_chain_exceptions` in the tool trace.

## Troubleshooting

- If API routes fail with missing relation errors, confirm the migration completed before rebuilding services.
- If the seed reports missing `WH-HYD`, check that Day 1 demo seed completed successfully. The seed is optional; the migration and blank forms still work without it.
- If the frontend shows an API error, inspect `docker compose logs --tail=100 api`.
- If MCP is unhealthy, inspect `docker compose logs --tail=100 mcp`.
- Never paste `.env` values or API keys into chat. Do not delete the database or Chroma volume.
