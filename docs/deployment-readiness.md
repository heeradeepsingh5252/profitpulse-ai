# Deployment Readiness and Production Blockers

Version: 1.0.0 demo review

## Current status

ProfitPulse AI is a locally runnable, Dockerized demonstration. It is not approved or configured for public production deployment.

The local environment has four services: PostgreSQL, FastAPI, React frontend served by Nginx, and MCP Streamable HTTP server.

## Blockers before production

### 1. Authentication and tenant authorization

The current `X-Organization-ID` value is caller-supplied. The frontend and MCP server use a fixed demo tenant.

Before production:
- Add real user authentication.
- Derive tenant identity from validated user/session claims.
- Enforce tenant authorization on every database and vector-store operation.
- Add cross-tenant isolation tests.
- Define user roles and permissions.

### 2. Network and MCP security

The local Compose setup publishes database, API and MCP ports on the host.

Before production:
- Keep PostgreSQL private to the application network.
- Put public traffic behind a controlled TLS reverse proxy or gateway.
- Define MCP authentication, origin policy and session lifecycle.
- Apply rate limits and request-size limits.
- Review CORS, network policy and firewall rules.

### 3. Secrets and configuration

The local `.env` file is excluded from Git. `.env.example` documents variable names.

Before production:
- Use a managed secrets store.
- Rotate all development credentials.
- Separate development, test and production configurations.
- Define secret rotation and incident-response procedures.
- Never expose provider keys in frontend bundles or logs.

### 4. Data protection and reliability

Before production:
- Define backup schedules and test database restoration.
- Define retention, deletion and export policies.
- Add database migration automation and rollback procedures.
- Add health, readiness and dependency monitoring.
- Define recovery objectives and incident runbooks.

### 5. AI and RAG quality

The current RAG distance threshold is calibrated against a small synthetic dataset.

Before production:
- Build a representative, permission-aware evaluation dataset.
- Measure retrieval relevance, citation correctness and answer faithfulness.
- Test prompt injection and malicious uploaded documents.
- Define model fallback, timeout, quota and cost controls.
- Log model usage without leaking confidential content.
- Require human review for consequential business decisions.

### 6. Financial and accounting validation

Financial calculations are a management-reporting prototype.

Before production:
- Validate classifications and calculations with qualified finance professionals.
- Reconcile outputs against authoritative accounting records.
- Complete missing cash-flow and statement functionality.
- Test currency, tax, rounding and period-boundary cases.
- Establish audit trails and approval controls.

Do not use this demo for audited reporting, tax filings, investment decisions or IPO eligibility determinations.

### 7. Supply-chain integrations

Shipment events are manually entered.

Before production:
- Integrate authenticated carrier or logistics-provider feeds.
- Validate event identity, timestamps and location provenance.
- Add retry, deduplication and stale-data handling.
- Validate goods receipts against purchase orders.
- Define accounting treatment for shipment charges and landed cost.

### 8. IPO Readiness workflow

The IPO checklist is a local planning prototype.

Before production:
- Persist tasks and ownership in a secured backend.
- Add audit history and evidence management.
- Validate applicable rules with qualified legal, accounting and merchant-banking professionals.
- Do not infer listing eligibility from the checklist score or selected route.

## Deployment recommendation

Keep the current application limited to local demonstrations with synthetic data until the blockers above are addressed and independently tested.
