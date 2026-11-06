"""Development MCP server for ProfitPulse. Tenant is pinned by environment, not tool input."""
from __future__ import annotations

import os
from datetime import date

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE_URL = os.getenv("MCP_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ORGANIZATION_ID = os.getenv("DEMO_ORGANIZATION_ID", "11111111-1111-4111-8111-111111111111")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

mcp = FastMCP("ProfitPulse AI", host=MCP_HOST, port=MCP_PORT)


def _headers() -> dict[str, str]:
    # Development-only: fixed demo tenant. Production must use authenticated tenant context.
    return {"X-Organization-ID": ORGANIZATION_ID}


def _request(method: str, path: str, **kwargs):
    try:
        response = httpx.request(method, f"{API_BASE_URL}{path}", headers=_headers(), timeout=30.0, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        return {"error": "ProfitPulse API request failed", "detail": str(exc)}


@mcp.tool()
def search_knowledge_base(query: str, top_k: int = 5) -> dict:
    """Search uploaded tenant knowledge documents; results include filename/page citations."""
    if not 1 <= top_k <= 10:
        return {"error": "top_k must be between 1 and 10"}
    return _request("POST", "/api/v1/knowledge/search", json={"query": query, "top_k": top_k})


@mcp.tool()
def get_monthly_financial_trend(start_date: str, end_date: str) -> dict:
    """Retrieve monthly financial trend from the tenant-scoped ProfitPulse API."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return {"error": "Dates must use YYYY-MM-DD format"}
    if end < start or (end - start).days > 1096:
        return {"error": "Invalid period; end_date must follow start_date and range must not exceed three years"}
    return _request("GET", "/api/v1/financial/monthly-trend", params={"start_date": start_date, "end_date": end_date})


@mcp.tool()
def get_supply_chain_overview() -> dict:
    """Summarize open purchase orders, inbound shipments, delays and transit-time KPIs."""
    return _request("GET", "/api/v1/supply-chain/overview")


@mcp.tool()
def get_inbound_shipments(status: str | None = None, limit: int = 20) -> dict:
    """List shipment origin, destination, carrier, ETA, status, tracking events and charges."""
    if not 1 <= limit <= 100:
        return {"error": "limit must be between 1 and 100"}
    params = {"limit": limit}
    if status:
        params["status"] = status
    return _request("GET", "/api/v1/supply-chain/shipments", params=params)


@mcp.tool()
def get_shipment_timeline(shipment_id: str) -> dict:
    """Retrieve recorded shipment milestones, associated products and recorded charges for one shipment UUID."""
    return _request("GET", f"/api/v1/supply-chain/shipments/{shipment_id}/timeline")


@mcp.tool()
def get_supplier_scorecards() -> dict:
    """Compare supplier on-time performance, fill rate, procurement lead time and rejected quantities."""
    return _request("GET", "/api/v1/supply-chain/supplier-scorecards")


@mcp.tool()
def get_supply_chain_exceptions() -> dict:
    """Retrieve delayed shipments, overdue ETAs and stale tracking exceptions."""
    return _request("GET", "/api/v1/supply-chain/exceptions")


@mcp.resource("profitpulse://capabilities")
def capabilities() -> str:
    """Describe the development server's exposed capabilities and scope."""
    return (
        "ProfitPulse AI MCP development server. Tools include knowledge search, monthly financial trends, "
        "supply-chain overview, inbound shipments, shipment timelines, supplier scorecards and supply-chain exceptions. "
        "Tenant is pinned to DEMO_ORGANIZATION_ID in the service "
        "environment. This is a local demonstration, not production authentication."
    )


@mcp.prompt()
def investigate_business_question(question: str) -> str:
    """Create a grounded investigation prompt for the connected ProfitPulse tenant."""
    return (
        f"Investigate this business question: {question}. Use available ProfitPulse tools. "
        "Separate retrieved facts from hypotheses, state dates and currency, and cite "
        "document passages with the exact filename/page citation returned by retrieval."
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
