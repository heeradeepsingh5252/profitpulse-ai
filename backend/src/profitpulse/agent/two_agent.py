"""Two-stage ProfitPulse intelligence workflow.

The Data Analyst stage produces deterministic, tenant-scoped facts from the
ledger, delivered order lines and inventory snapshots. The Business Analyst
stage interprets those facts and can use the existing read-only LangGraph tools
for additional operational and company-knowledge evidence.
"""
import json
from datetime import date
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.messages import AIMessage, ToolMessage

from profitpulse.agent.graph import AgentExecutionError, _content_to_text, build_agent_graph
from profitpulse.agent.llm import LLMConfigurationError, build_chat_model
from profitpulse.analytics import load_inventory_health, load_product_performance
from profitpulse.db import organization_connection
from profitpulse.financial import load_financial_summary, load_monthly_financial_trend


def _number(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _change_pct(current: Any, previous: Any) -> float | None:
    prior = _number(previous)
    if prior == 0:
        return None
    return round((_number(current) - prior) / abs(prior) * 100, 2)


def build_data_analyst_report(
    *,
    period_start: date,
    period_end: date,
    currency: str,
    metrics: dict[str, Any],
    monthly_trend: list[dict[str, Any]],
    products: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build auditable findings from already-computed database results."""
    findings: list[dict[str, Any]] = []

    revenue = _number(metrics.get("net_revenue"))
    gross_profit = _number(metrics.get("gross_profit"))
    ebitda = _number(metrics.get("ebitda"))
    expense_ratio = metrics.get("operating_expense_ratio_pct")
    gross_margin = metrics.get("gross_margin_pct")

    findings.append({
        "id": "revenue",
        "title": "Net revenue",
        "detail": f"Net revenue for the selected period was {currency} {revenue:,.2f}.",
        "severity": "info",
        "evidence": "Posted general-ledger entries for the selected period.",
    })
    if gross_margin is not None:
        findings.append({
            "id": "gross-margin",
            "title": "Gross margin",
            "detail": f"Gross margin was { _number(gross_margin):.2f}% on net revenue of {currency} {revenue:,.2f}.",
            "severity": "info",
            "evidence": "Gross profit divided by net revenue, using the financial summary calculation.",
        })

    findings.append({
        "id": "operating-result",
        "title": "Operating result",
        "detail": (
            f"EBITDA was {currency} {ebitda:,.2f}, which is "
            f"{'negative' if ebitda < 0 else 'positive' if ebitda > 0 else 'break-even'} "
            "for the selected period."
        ),
        "severity": "watch" if ebitda < 0 else "info",
        "evidence": "Gross profit less operating expenses; EBITDA is not cash flow or net profit.",
    })
    if expense_ratio is not None:
        findings.append({
            "id": "expense-ratio",
            "title": "Operating expense ratio",
            "detail": f"Operating expenses were {_number(expense_ratio):.2f}% of net revenue.",
            "severity": "watch" if _number(expense_ratio) > 100 else "info",
            "evidence": "Operating expenses divided by net revenue.",
        })

    if len(monthly_trend) >= 2:
        previous, latest = monthly_trend[-2], monthly_trend[-1]
        revenue_change = _change_pct(latest.get("net_revenue"), previous.get("net_revenue"))
        expense_change = _change_pct(latest.get("operating_expenses"), previous.get("operating_expenses"))
        trend_parts = []
        if revenue_change is not None:
            trend_parts.append(f"net revenue changed {revenue_change:+.2f}%")
        if expense_change is not None:
            trend_parts.append(f"operating expenses changed {expense_change:+.2f}%")
        if trend_parts:
            findings.append({
                "id": "monthly-trend",
                "title": "Latest month movement",
                "detail": f"From {previous.get('month')} to {latest.get('month')}, " + " and ".join(trend_parts) + ".",
                "severity": "info",
                "evidence": "Like-for-like comparison of the two latest monthly ledger periods returned.",
            })

    ranked_products = sorted(products, key=lambda item: _number(item.get("gross_profit")), reverse=True)
    if ranked_products:
        top = ranked_products[0]
        findings.append({
            "id": "product-contribution",
            "title": "Highest gross-profit product",
            "detail": (
                f"{top.get('product_name', 'The leading product')} generated "
                f"{currency} {_number(top.get('gross_profit')):,.2f} gross profit "
                f"from {_number(top.get('units_sold')):,.0f} units sold."
            ),
            "severity": "info",
            "evidence": "Delivered order-item lines for the selected period; product-level line basis.",
        })
        negative_products = [item for item in products if _number(item.get("gross_profit")) < 0]
        if negative_products:
            findings.append({
                "id": "negative-product-margin",
                "title": "Products with negative gross profit",
                "detail": ", ".join(str(item.get("product_name", item.get("sku", "Unknown product"))) for item in negative_products),
                "severity": "critical",
                "evidence": "Delivered order-item lines where line sales less line-level cost was below zero.",
            })

    reorder_items = [item for item in inventory if item.get("reorder_alert") is True]
    findings.append({
        "id": "inventory-reorder",
        "title": "Reorder-level inventory",
        "detail": (
            f"{len(reorder_items)} SKU(s) are at or below their configured reorder level."
            if reorder_items
            else "No SKU was at or below its configured reorder level in the returned inventory snapshot."
        ),
        "severity": "watch" if reorder_items else "info",
        "evidence": "Latest available inventory snapshot on or before the selected period end date.",
    })

    snapshot_dates = sorted({
        str(item.get("snapshot_date"))
        for item in inventory
        if item.get("snapshot_date") is not None
    })
    return {
        "status": "completed",
        "agent": "AI Data Analyst",
        "period": {"start_date": str(period_start), "end_date": str(period_end)},
        "currency": currency,
        "summary": (
            f"Reviewed the selected financial period, {len(monthly_trend)} monthly ledger period(s), "
            f"{len(products)} product record(s), and {len(inventory)} inventory record(s)."
        ),
        "metrics": {
            "net_revenue": metrics.get("net_revenue"),
            "gross_profit": metrics.get("gross_profit"),
            "gross_margin_pct": metrics.get("gross_margin_pct"),
            "operating_expenses": metrics.get("operating_expenses"),
            "operating_expense_ratio_pct": metrics.get("operating_expense_ratio_pct"),
            "ebitda": metrics.get("ebitda"),
            "ebitda_margin_pct": metrics.get("ebitda_margin_pct"),
            "pat": metrics.get("pat"),
        },
        "findings": findings,
        "data_sources": [
            "Posted general-ledger entries",
            "Monthly financial trend",
            "Delivered order-item lines",
            "Inventory snapshots and configured reorder levels",
        ],
        "inventory_snapshot_dates": snapshot_dates,
    }


def run_two_agent_analysis(
    *,
    question: str,
    organization_id: str,
    start_date: date,
    end_date: date,
    max_tool_rounds: int = 6,
) -> dict[str, Any]:
    """Run deterministic Data Analyst work followed by Business Analyst reasoning."""
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    try:
        with organization_connection(organization_id) as conn:
            org = conn.execute(
                "SELECT base_currency FROM organizations WHERE id = %s",
                (organization_id,),
            ).fetchone()
            currency = str(org["base_currency"]).strip() if org else ""
            metrics = load_financial_summary(conn, organization_id, start_date, end_date)
            monthly = load_monthly_financial_trend(conn, organization_id, start_date, end_date)
            products = load_product_performance(conn, organization_id, start_date, end_date, limit=20)
            inventory = load_inventory_health(conn, organization_id, end_date)

        data_report = build_data_analyst_report(
            period_start=start_date,
            period_end=end_date,
            currency=currency or "currency not configured",
            metrics=metrics,
            monthly_trend=monthly,
            products=products,
            inventory=inventory,
        )

        provider, model_name, chat_model = build_chat_model()
        graph, tools = build_agent_graph(chat_model, organization_id)
        tool_names = {tool.name for tool in tools}
        handoff = {
            "user_question": question,
            "period": data_report["period"],
            "verified_data_analyst_report": data_report,
        }
        instruction = (
            "You are now acting as the ProfitPulse AI Business Analyst, the second specialist in a two-agent workflow. "
            "The Data Analyst has completed deterministic calculations from tenant-scoped records. "
            "Treat the attached report as verified analytical evidence. Interpret it for a manufacturing SME owner, "
            "explain business implications, separate facts from hypotheses, and give prioritised practical next steps. "
            "You may use your existing read-only tools for additional evidence from financial, operational, supply-chain "
            "and company-knowledge sources. Do not repeat calculations that are already present unless a tool is needed "
            "to verify them. Never invent production metrics, machine utilisation, wastage, capacity, supplier causes, "
            "cash-flow amounts or savings when those are not in the evidence. State when production data is not connected. "
            "Answer in clear English with concise headings: What the data says; Business interpretation; Recommended actions; "
            "Data limitations. Do not expose private chain-of-thought."
        )
        result = graph.invoke(
            {"messages": [HumanMessage(content=instruction + "\n\n" + json.dumps(handoff, ensure_ascii=False, default=str))]},
            config={"recursion_limit": max(8, max_tool_rounds * 2 + 4)},
        )

        messages = result.get("messages", [])
        final_message = messages[-1] if messages else None
        answer = _content_to_text(getattr(final_message, "content", ""))
        if not answer:
            answer = "The Business Analyst could not produce a recommendation from the available evidence."

        trace = []
        sources = []
        seen_source_keys = set()
        for message in messages:
            if isinstance(message, AIMessage):
                for call in getattr(message, "tool_calls", []) or []:
                    if call.get("name") in tool_names:
                        trace.append({
                            "tool": call.get("name"),
                            "arguments": call.get("args", {}),
                        })
            if isinstance(message, ToolMessage) and getattr(message, "name", "") == "search_knowledge_base":
                raw = _content_to_text(getattr(message, "content", ""))
                try:
                    payload = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                for hit in payload.get("results", []) if isinstance(payload, dict) else []:
                    source = hit.get("source", {}) if isinstance(hit, dict) else {}
                    key = (source.get("document_id"), source.get("page_number"), source.get("filename"))
                    if source and key not in seen_source_keys:
                        seen_source_keys.add(key)
                        sources.append(source)

        business_report = {
            "status": "completed",
            "agent": "AI Business Analyst",
            "answer": answer,
            "provider": provider,
            "model": model_name,
            "tools_used": list(dict.fromkeys(item["tool"] for item in trace)),
            "tool_trace": trace,
            "sources": sources,
        }
        return {
            "analysis_id": str(uuid4()),
            "period": data_report["period"],
            "currency": currency,
            "data_analyst": data_report,
            "business_analyst": business_report,
            "answer": answer,
            "provider": provider,
            "model": model_name,
            "tools_used": business_report["tools_used"],
            "tool_trace": trace,
            "sources": sources,
            "disclaimer": (
                "Decision support based on the connected demo ledger, operational records and any cited company documents. "
                "Not audited financial, tax, legal, investment or professional advice."
            ),
        }
    except (LLMConfigurationError, AgentExecutionError):
        raise
    except Exception as exc:
        raise AgentExecutionError(
            "The two-agent investigation could not be completed. Check the database, provider configuration and API logs."
        ) from exc
