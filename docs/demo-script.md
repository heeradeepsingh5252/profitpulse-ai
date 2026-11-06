# ProfitPulse AI Demo Script

Suggested duration: 3–5 minutes  
Environment: Local Docker Compose demo  
Data: Synthetic

## 1. Opening: business overview

Open `http://localhost:3000`.

Introduce ProfitPulse AI as a small-business intelligence demonstration combining financial analytics, operational reporting, a document knowledge base, an AI tool-calling workflow and supply-chain visibility.

Clarify that all seeded business records are synthetic.

## 2. Financial intelligence

Open the executive dashboard and financial views. Walk through revenue, gross margin, operating expenses, EBITDA, monthly trends, budget variance and financial ratios.

Use August–October 2026 as the seeded demonstration period. The sample business has falling revenue and widening operating losses during this period. Do not present the sample statements as audited accounts.

## 3. Ask the AI business analyst

Open the AI analyst interface and ask:

`Summarize the recent financial trend and identify the main operating concern.`

Explain that the LangGraph workflow calls predefined business tools. Model output depends on the configured Groq account, network access and usage limits.

## 4. Demonstrate RAG

Use `demo_expense_approval_policy.md` and ask:

`What approval is required for an unbudgeted purchase of INR 75,000?`

The synthetic policy says purchases above INR 25,000 and up to INR 100,000 require finance-lead approval. Show the filename and page citation returned by retrieval. Explain that the document is sample training content, not a real company policy.

## 5. Supply-chain intelligence

Open Supply Chain and show open purchase orders, outstanding quantities, inbound shipment status, a delayed shipment, a shipment timeline, recorded freight charge and supplier scorecards.

The demonstration includes a delayed Prime Goods shipment from Mumbai to Hyderabad, with synthetic tracking events and recorded charges. Tracking events are entered manually. No live carrier integration is connected.

## 6. IPO Readiness

Open the IPO Readiness module. Explain that it is a planning checklist for organizing readiness work. Its tasks and route selection are not an eligibility determination or legal opinion.

The checklist is stored in browser local storage in this prototype, not centrally in PostgreSQL.

## 7. Close

Summarize the architecture: React and TypeScript frontend, FastAPI, PostgreSQL, LangGraph and Groq, ChromaDB-backed RAG, MCP Streamable HTTP, and deterministic financial and supply-chain calculations.

Close with future engineering priorities: authentication, tenant isolation, automated evaluation, observability, security hardening and real integrations.

## Demo safety notes

Use synthetic records only. Do not upload customer data, production credentials or confidential company documents. Do not expose local development services publicly.
