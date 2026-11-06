# ProfitPulse AI: Portfolio Case Study

## Project summary

ProfitPulse AI is a synthetic-data SME Business Intelligence demonstration built to show how business data, company documents and operational workflows can be connected into a decision-support application.

It combines deterministic analytics with an LLM-backed tool-calling workflow, retrieval-augmented generation and an MCP integration boundary.

## Business problem

Small businesses may have financial records, product data, operational metrics and internal policy documents spread across separate tools. This project demonstrates a single interface for exploring selected business metrics and retrieving supporting business-document content.

The project does not claim measured customer adoption, revenue uplift or cost savings.

## Solution

The demonstration includes:
- Financial reporting and trend analysis.
- Inventory, product and regional analytics.
- A LangGraph agent using predefined read-only business tools.
- ChromaDB-backed document retrieval with filename/page citations.
- MCP tools for knowledge, financial and supply-chain queries.
- Supplier, purchase-order and inbound-shipment workflows.
- Supplier scorecards and manually recorded shipment exceptions.
- An IPO Readiness planning checklist.

## Architecture

### Frontend

React, TypeScript, Vite, Recharts and Lucide React. Nginx serves the production build and proxies API requests.

### Backend

FastAPI provides business APIs. PostgreSQL stores tenant-scoped business records.

### AI and retrieval

LangGraph orchestrates predefined tools and a Groq-backed model. ChromaDB stores document chunks and supports organization-scoped retrieval.

### Integration

The MCP server exposes Streamable HTTP tools that call the existing FastAPI endpoints instead of duplicating business logic.

### Runtime

Docker Compose runs PostgreSQL, API, frontend and MCP services locally.

## Demonstrated implementation

The local test session verified:
- Eight core API checks returned HTTP 200 with the demo organization context.
- Seven MCP tools were discovered and invoked successfully.
- Knowledge search returned `demo_expense_approval_policy.md` with a page citation.
- The backend suite reported 63 passed tests.
- The frontend production build completed successfully.
- The frontend npm audit reported zero vulnerabilities after the Vite security update.

These are local engineering verification results, not production service-level measurements.

## Example synthetic business observations

The seeded August–October 2026 data showed declining monthly revenue and increasing operating losses.

Supply-chain examples included two open purchase orders, ₹178,000 open purchase-order goods value, 140 outstanding units, one delayed inbound shipment and supplier-specific fill-rate differences. All values are synthetic demo records.

## Engineering decisions

1. Deterministic calculations remain the source for defined financial and operational metrics.
2. The LLM uses predefined tools instead of unrestricted database access.
3. RAG retrieval returns source metadata to support grounded answers.
4. MCP delegates to existing APIs rather than reimplementing business logic.
5. New features were frozen before release hardening to prioritize reliability and security review.

## Limitations

- No production authentication or verified tenant authorization.
- Fixed demo tenant in frontend and MCP configuration.
- Manual shipment events; no live carrier/GPS/EDI/customs feed.
- Synthetic financial and supply-chain records.
- RAG relevance threshold calibrated on a small demo set.
- IPO checklist stored in browser local storage.
- Financial outputs are not audited or professionally certified.

## What this project demonstrates

The project demonstrates full-stack integration, API design, SQL-backed analytics, tool-calling workflows, RAG, MCP, Docker-based packaging, test automation and release hygiene.

It should be presented as a working portfolio prototype, not a production-certified enterprise platform.
