# Day 4 — Agentic RAG, ChromaDB and MCP

## What is included

- PDF, TXT, Markdown and CSV text ingestion, with page-aware chunk metadata.
- ChromaDB persistent vector storage mounted at `/app/data/chroma`.
- Organization metadata filters on every search, list and delete operation.
- A `search_knowledge_base` LangGraph tool for the existing business agent.
- Source citations formatted as `[filename, p. N]` and returned separately in retrieval results.
- A standalone MCP server exposing `search_knowledge_base` and `get_monthly_financial_trend` over Streamable HTTP.
- Synthetic expense-approval policy for smoke testing.

## API endpoints

All endpoints require `X-Organization-ID` in this development build.

- `POST /api/v1/knowledge/documents` — multipart upload field `file`.
- `POST /api/v1/knowledge/search` — JSON `{ "query": "...", "top_k": 5 }`.
- `GET /api/v1/knowledge/documents` — list documents for the current tenant.
- `DELETE /api/v1/knowledge/documents/{document_id}` — tenant-scoped deletion.
- `POST /api/v1/agent/ask` — the business agent can call `search_knowledge_base` when document evidence is relevant.

## Build and start

```bash
docker compose build --no-cache api mcp
docker compose up -d --force-recreate api mcp
docker compose ps
docker compose exec api pytest -q
```

First document ingestion may download Chroma's default local ONNX embedding model. Allow network access from the API container for that first run. The embedding model then uses local inference; Groq remains the answer-generation model.

## Upload the sample document

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/documents \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' \
  -F 'file=@examples/knowledge/demo_expense_approval_policy.md' | python3 -m json.tool
```

## Search the knowledge base

```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/search \
  -H 'Content-Type: application/json' \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' \
  -d '{"query":"Who must approve an unbudgeted purchase above INR 25,000?","top_k":4}' \
  | python3 -m json.tool
```

## Ask the AI agent

```bash
curl -s -X POST http://localhost:8000/api/v1/agent/ask \
  -H 'Content-Type: application/json' \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' \
  -d '{"question":"According to our uploaded expense policy, who approves an unbudgeted purchase of INR 40,000? Cite the exact document and page. Separate policy evidence from recommendations."}' \
  | python3 -m json.tool
```

## MCP connection

MCP Streamable HTTP endpoint: `http://localhost:8001/mcp`.

MCP tools:

- `search_knowledge_base(query, top_k)`
- `get_monthly_financial_trend(start_date, end_date)`

Test with the MCP Inspector or another MCP-compatible client. For a local Inspector using the default HTTP transport, connect to the endpoint above.

## Security and boundaries

- The local `X-Organization-ID` header remains a development-only tenant selector, not authentication.
- Chroma filters all query/list/delete operations by the request organization ID. The LLM does not receive an organization ID parameter.
- The MCP demo service pins one organization ID from its environment. Do not expose it publicly or use it for multiple customers until MCP authentication and verified tenant context are implemented.
- Scanned PDFs are rejected because OCR is not included. No OCR, external embedding API, or automatic policy interpretation is implied.
- Retrieved text is untrusted. It may support answers but cannot override system instructions or access controls.
- This remains a local prototype. Production requires auth, authorization, audit logs, upload malware scanning, encrypted storage, retention controls, backup/restore, rate limits and security review.
