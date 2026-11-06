# Day 3 — ProfitPulse AI Business Analyst

Day 3 adds a bounded LangGraph tool-calling agent to the existing Day 1/Day 2 application.

## What it does

- Accepts a natural-language business question through `POST /api/v1/agent/ask`.
- Uses Gemini or Groq through LangChain chat integrations.
- Uses LangGraph `StateGraph`, `ToolNode` and `tools_condition` for an agent/tool loop.
- Exposes nine predefined, tenant-bound, read-only business analytics tools.
- Returns the answer, provider/model metadata and a trace of tool names/arguments.

## Safety design

- The LLM does not receive an `organization_id` argument. Tools close over the organization selected by the API dependency.
- The LLM cannot issue arbitrary SQL. It only selects predefined, parameterized analytics tools.
- Date ranges are validated and limited to approximately three years per tool call.
- Tool calls are bounded by LangGraph's recursion limit.
- The local `X-Organization-ID` header remains a demo-only tenant selector. Do not expose this API to customers or the public internet without authenticated identity, membership checks and a security review.
- This agent is decision support, not accounting, tax, legal, investment, lending or IPO advice.
- Do not send real customer financial data to an API provider until data-handling, retention, access and contractual requirements have been reviewed.

## Configure an LLM provider

Add one provider configuration to your existing `.env`. Do not overwrite `.env` and do not commit API keys.

Gemini:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
```

Or Groq:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

The defaults use the current stable Gemini Flash model and a current Groq production tool-use model at the time this bundle was prepared. Model identifiers can change; if your provider console lists a replacement, change the environment variable rather than editing Python code.

## Rebuild the API

From the existing project root:

```bash
docker compose up --build -d api
docker compose ps
docker compose logs --tail=100 api
```

Restarting the API does not delete the PostgreSQL volume. Do not run `docker compose down -v`.

## Verify

```bash
# Health and capability list
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/agent/capabilities

# Automated tests
docker compose exec api pytest -q

# Live AI request (requires provider key in .env)
curl -sS -X POST http://localhost:8000/api/v1/agent/ask \
  -H 'Content-Type: application/json' \
  -H 'X-Organization-ID: 11111111-1111-4111-8111-111111111111' \
  -d '{"question":"Why is EBITDA negative for August through October 2026? Use the financial summary and product performance data to investigate.","max_tool_rounds":6}'
```

If no key is configured, the endpoint returns HTTP 503 with a clear configuration message. Provider/network errors return HTTP 502 without exposing secrets or raw tracebacks.

## Available tools

1. `get_data_coverage`
2. `get_financial_summary`
3. `get_balance_sheet`
4. `get_financial_ratios`
5. `get_product_performance`
6. `get_regional_performance`
7. `get_inventory_health`
8. `get_monthly_financial_trend`
9. `get_expense_breakdown`
10. `get_budget_variance`

The system prompt requires numeric claims to be based on tool outputs, asks the model to distinguish facts from hypotheses, and instructs it to identify missing data rather than invent it.

## API response

Successful responses include:

- `answer`: business explanation
- `provider` and `model`: server-selected LLM configuration
- `tools_used`: unique tools selected by the model
- `tool_trace`: tool names and arguments for observability
- `tool_result_count`: number of tool result messages
- `disclaimer`: decision-support boundary

## Current limitations

- No conversation memory/persistent threads yet.
- No document RAG yet; that is a later milestone.
- No autonomous action or write access to business systems.
- Demo tenant selection is not production authentication.
- Tool traces do not expose full tool outputs in the API response.
- The agent can call the tools, but factual quality still needs a benchmark with expected answers and a real provider key.
