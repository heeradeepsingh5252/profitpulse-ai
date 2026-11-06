# Security Review

Review scope: local ProfitPulse AI demo, version 1.0.0

## Summary

This review records the observed local-development security controls and remaining limitations. It is not a penetration test, formal audit or production security certification.

## Controls observed

### Repository hygiene

- `.env` is excluded from Git.
- `.env.example` is retained as a configuration template.
- Local backups, dependency folders and build artifacts are ignored.
- The credential-pattern scan flagged a PostgreSQL role-creation script. Inspection showed it references `APP_DB_PASSWORD` and uses `psql` variable substitution; the inspection output did not reveal a hard-coded password.
- A pattern scan is not proof that every secret has been eliminated.

### Frontend dependencies

The frontend dependency audit reported zero vulnerabilities after updating Vite to 6.4.5 and esbuild to 0.25.12. Production-only npm audit also reported zero vulnerabilities.

### Backend boundaries

The LLM agent uses predefined tools. SQL access is guarded by application logic. The MCP server calls the backend API instead of independently implementing business queries.

### Tenant context

Business routes require an organization identifier. In this demo it is supplied through `X-Organization-ID`, which is caller-controlled. This is not a secure authorization mechanism.

## Known security limitations

1. No login or production authentication is configured.
2. The frontend uses a fixed demo organization ID.
3. MCP is pinned to a fixed demo organization.
4. MCP has no production authentication or origin policy.
5. Local Compose publishes database, API and MCP ports to the host.
6. ChromaDB uses a local persistent volume and a small demo retrieval dataset.
7. Uploaded document safety, prompt-injection resistance and retrieval access controls need production-grade evaluation.
8. No independent penetration test or formal threat-model review has been completed.

## Required remediation

Before using real company data:
- Implement authentication and role-based authorization.
- Enforce tenant scope from trusted identity claims.
- Restrict network exposure and require TLS.
- Move secrets into a managed secrets store and rotate development credentials.
- Add rate limits, audit logs and monitoring.
- Test cross-tenant access and document-level permissions.
- Evaluate prompt injection and unsafe tool invocation.
- Establish backup, restore and incident-response procedures.

## Dependency caveat

A clean `npm audit` is limited to the dependency tree and advisories known to the registry at the time of the check. It does not prove application security or cover backend container images and Python dependencies.

## Data handling rule

Use synthetic demo records only. Do not connect confidential financial records, customer documents or production credentials to this local prototype.
