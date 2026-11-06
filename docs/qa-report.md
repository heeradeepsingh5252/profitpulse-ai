# ProfitPulse AI QA Report

Test environment: Local macOS development machine with Docker Compose  
Recorded test session: 6 November 2026  
Dataset: Synthetic demo organization

## Results observed before final version metadata edits

### Docker and services

- `docker compose config --quiet`: passed.
- PostgreSQL container reported healthy.
- FastAPI health endpoint returned HTTP 200.
- Frontend returned HTTP 200.
- PostgreSQL `pg_isready`: accepting connections.
- MCP Streamable HTTP initialization returned HTTP 200.
- MCP initialized notification returned HTTP 202.

The frontend was subsequently rebuilt and reported Docker health `healthy`, with HTTP 200.

### Core API smoke tests

With `X-Organization-ID: 11111111-1111-4111-8111-111111111111`, eight checks returned HTTP 200:

- Database health.
- Dashboard summary.
- Agent capabilities.
- Current organization.
- Knowledge documents.
- Supply-chain overview.
- Supplier scorecards.
- Financial monthly trend for August–October 2026.

Business and knowledge routes returned HTTP 422 when the required organization header was omitted. This is expected request validation in the current local configuration.

### Backend automated tests

Command:

```bash
 docker compose exec -T api python -m pytest -q
```

Recorded result: `63 passed, 1 warning`.

The warning is a Starlette/AnyIO deprecation warning involving `anyio.abc.BlockingPortal`. It did not fail tests.

### MCP integration

The MCP server initialized using protocol version `2025-03-26`, advertised seven tools and successfully executed each:

1. `search_knowledge_base`
2. `get_monthly_financial_trend`
3. `get_supply_chain_overview`
4. `get_inbound_shipments`
5. `get_shipment_timeline`
6. `get_supplier_scorecards`
7. `get_supply_chain_exceptions`

The RAG search returned one relevant chunk from `demo_expense_approval_policy.md` with citation `[demo_expense_approval_policy.md, p. 1]`.

The first RAG call timed out during the initial embedding-model download. A retry after the download completed succeeded.

### Frontend build and dependencies

After updating Vite:
- Vite: `6.4.5`
- esbuild: `0.25.12`
- `npm audit`: zero vulnerabilities.
- `npm audit --omit=dev`: zero vulnerabilities.
- `npm run build`: successful.
- TypeScript check: successful.
- Vite transformed 2,244 modules.

The minified JavaScript bundle was approximately 879 KB, exceeding Vite's 500 KB advisory threshold. This is a performance optimization item, not a build failure.

### Docker frontend rebuild

The frontend image was rebuilt and restarted. The container subsequently reported `healthy`, and `http://localhost:3000` returned HTTP 200.

## Final retest after release metadata edits

The following changes were made after the initial test run and have since been revalidated:
- Backend API version metadata changed to `1.0.0`.
- Frontend package version changed to `1.0.0`.
- Frontend Dockerfile changed to use `npm ci` with `package-lock.json`.

Rerun the backend test suite, frontend build, Docker frontend build and health checks after these changes before attaching a final release tag.

## Scope limitations

This is a local functional smoke-test report. It is not load testing, penetration testing, accounting validation, disaster-recovery testing or production acceptance testing.
