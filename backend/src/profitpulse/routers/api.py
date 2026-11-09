import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator, model_validator

from profitpulse.config import MAX_CSV_BYTES
from profitpulse.db import organization_connection
from profitpulse.analytics import (
    load_inventory_health,
    load_product_performance,
    load_regional_performance,
)
from profitpulse.financial import (
    compute_financial_ratios,
    load_balance_sheet,
    load_budget_variance,
    load_financial_summary,
    load_monthly_financial_trend,
)
from profitpulse.ingestion.csv_importer import parse_csv
from profitpulse.supply_chain import (
    load_purchase_orders, load_shipment_timeline, load_shipments,
    load_supplier_scorecards, load_supplier_sites, load_supply_chain_exceptions,
    load_supply_chain_overview,
)
from profitpulse.agent.graph import AgentExecutionError, run_agent
from profitpulse.agent.llm import LLMConfigurationError

router = APIRouter(prefix="/api/v1")


def tenant_id(x_organization_id: UUID = Header(..., alias="X-Organization-ID")) -> str:
    """Development-only tenant selector. Replace with authenticated membership lookup."""
    return str(x_organization_id)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1500)
    top_k: int = Field(default=5, ge=1, le=10)


class AgentAskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=3000)
    max_tool_rounds: int = Field(default=6, ge=1, le=8)


class TwoAgentAnalysisRequest(BaseModel):
    question: str = Field(default="Review the manufacturing business performance and identify the most important actions.", min_length=5, max_length=3000)
    start_date: date = Field(default=date(2026, 8, 1))
    end_date: date = Field(default=date(2026, 10, 31))
    max_tool_rounds: int = Field(default=6, ge=1, le=8)

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class SupplierSiteRequest(BaseModel):
    site_code: str = Field(min_length=2, max_length=40)
    site_name: str = Field(min_length=2, max_length=160)
    site_type: Literal["factory", "warehouse", "distribution_center", "port", "other"] = "factory"
    origin_city: str = Field(min_length=2, max_length=120)
    origin_state: str | None = Field(default=None, max_length=120)
    origin_country: str = Field(min_length=2, max_length=100)
    origin_country_code: str | None = Field(default=None, min_length=2, max_length=2)
    origin_postal_code: str | None = Field(default=None, max_length=24)
    origin_port: str | None = Field(default=None, max_length=120)
    default_lead_time_days: int | None = Field(default=None, ge=0, le=730)
    preferred_transport_mode: Literal["road", "rail", "air", "sea", "courier", "multimodal"] | None = None
    is_primary: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class PurchaseOrderItemRequest(BaseModel):
    product_id: UUID
    quantity_ordered: Decimal = Field(gt=0, le=1000000000)
    unit_cost: Decimal = Field(ge=0, le=1000000000)


class PurchaseOrderCreateRequest(BaseModel):
    supplier_id: UUID
    po_number: str = Field(min_length=2, max_length=80)
    order_date: date
    expected_date: date | None = None
    items: list[PurchaseOrderItemRequest] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_unique_products(self):
        product_ids = [item.product_id for item in self.items]
        if len(set(product_ids)) != len(product_ids):
            raise ValueError("purchase order items must not contain duplicate product_id values")
        return self


class ShipmentLineRequest(BaseModel):
    purchase_order_item_id: UUID
    quantity_shipped: Decimal = Field(gt=0, le=1000000000)


class ShipmentCreateRequest(BaseModel):
    shipment_number: str = Field(min_length=2, max_length=80)
    supplier_id: UUID
    supplier_site_id: UUID | None = None
    purchase_order_ids: list[UUID] = Field(min_length=1, max_length=100)
    destination_warehouse_id: UUID
    origin_city: str | None = Field(default=None, max_length=120)
    origin_state: str | None = Field(default=None, max_length=120)
    origin_country: str | None = Field(default=None, max_length=100)
    origin_country_code: str | None = Field(default=None, min_length=2, max_length=2)
    origin_port: str | None = Field(default=None, max_length=120)
    destination_port: str | None = Field(default=None, max_length=120)
    carrier_name: str | None = Field(default=None, max_length=160)
    carrier_service: str | None = Field(default=None, max_length=120)
    tracking_number: str | None = Field(default=None, max_length=160)
    transport_mode: Literal["road", "rail", "air", "sea", "courier", "multimodal"]
    incoterm: Literal["EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF"] | None = None
    planned_departure_at: datetime | None = None
    promised_arrival_at: datetime | None = None
    current_eta_at: datetime | None = None
    items: list[ShipmentLineRequest] = Field(default_factory=list, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("planned_departure_at", "promised_arrival_at", "current_eta_at")
    @classmethod
    def require_timezone_aware_datetimes(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Datetime values must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_unique_lines(self):
        if self.planned_departure_at and self.promised_arrival_at and self.promised_arrival_at < self.planned_departure_at:
            raise ValueError("promised_arrival_at cannot be before planned_departure_at")
        if self.current_eta_at and self.planned_departure_at and self.current_eta_at < self.planned_departure_at:
            raise ValueError("current_eta_at cannot be before planned_departure_at")
        if len(set(self.purchase_order_ids)) != len(self.purchase_order_ids):
            raise ValueError("purchase_order_ids must not contain duplicates")
        item_ids = [line.purchase_order_item_id for line in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("shipment items must not contain duplicate purchase_order_item_id values")
        return self


class ShipmentEventRequest(BaseModel):
    event_code: Literal["booked", "picked_up", "departed_origin", "in_transit", "arrived_origin_port", "customs_started", "customs_cleared", "departed_port", "arrived_destination_port", "out_for_delivery", "arrived_warehouse", "delayed", "exception", "note"]
    occurred_at: datetime | None = None
    current_eta_at: datetime | None = None
    location_name: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("occurred_at", "current_eta_at")
    @classmethod
    def require_timezone_aware_datetimes(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Datetime values must include a timezone offset")
        return value


class ShipmentCostRequest(BaseModel):
    cost_type: Literal["freight", "insurance", "customs_duty", "customs_brokerage", "port_handling", "inland_transport", "other"]
    description: str | None = Field(default=None, max_length=500)
    amount: Decimal = Field(gt=0, le=1000000000000)
    charge_date: date
    reference: str | None = Field(default=None, max_length=120)


class GoodsReceiptLineRequest(BaseModel):
    shipment_item_id: UUID
    quantity_received: Decimal = Field(gt=0, le=1000000000)
    quantity_accepted: Decimal = Field(ge=0, le=1000000000)
    quantity_rejected: Decimal = Field(ge=0, le=1000000000)
    inspection_notes: str | None = Field(default=None, max_length=1000)


class GoodsReceiptRequest(BaseModel):
    receipt_number: str = Field(min_length=2, max_length=80)
    received_at: datetime
    inspection_status: Literal["pending", "passed", "partial", "failed"] = "pending"
    notes: str | None = Field(default=None, max_length=2000)
    items: list[GoodsReceiptLineRequest] = Field(min_length=1, max_length=500)

    @field_validator("received_at")
    @classmethod
    def require_timezone_aware_received_at(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validate_unique_receipt_lines(self):
        item_ids = [line.shipment_item_id for line in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("receipt items must not contain duplicate shipment_item_id values")
        for line in self.items:
            if line.quantity_accepted + line.quantity_rejected != line.quantity_received:
                raise ValueError("accepted plus rejected quantity must equal quantity_received")
        return self


@router.get("/agent/capabilities")
def agent_capabilities():
    """Describe the analytics tools available to the ProfitPulse agent."""
    return {
        "agent": "ProfitPulse AI Business Analyst",
        "orchestration": "LangGraph tool-calling workflow",
        "providers": ["groq"],
        "tools": [
            {"name": "get_data_coverage", "purpose": "Discover available financial, order and inventory data periods."},
            {"name": "get_financial_summary", "purpose": "Calculate net revenue, COGS, gross profit, EBITDA, EBIT, PBT and PAT."},
            {"name": "get_balance_sheet", "purpose": "Retrieve assets, liabilities, equity and balance check."},
            {"name": "get_financial_ratios", "purpose": "Calculate profitability, return, leverage and coverage ratios."},
            {"name": "get_expense_breakdown", "purpose": "Break down operating expenses by ledger account."},
            {"name": "get_monthly_expense_breakdown", "purpose": "Compare operating expenses by ledger account month by month."},
            {"name": "get_product_performance", "purpose": "Rank product sales, gross profit and units sold."},
            {"name": "get_regional_performance", "purpose": "Compare sales and gross profit by region."},
            {"name": "get_inventory_health", "purpose": "Inspect inventory snapshots and reorder alerts."},
            {"name": "get_monthly_financial_trend", "purpose": "Compare monthly P&L metrics."},
            {"name": "get_budget_variance", "purpose": "Compare actual financial measures with exact-period budgets."},
            {"name": "search_knowledge_base", "purpose": "Retrieve tenant-scoped document passages with filename and page citations."},
            {"name": "get_supply_chain_overview", "purpose": "Summarize open purchase orders, inbound shipments, overdue shipments and transit-time metrics."},
            {"name": "get_inbound_shipments", "purpose": "Inspect shipment origins, destinations, carriers, ETAs, tracking events and shipment costs."},
            {"name": "get_shipment_timeline", "purpose": "Retrieve recorded shipment milestones, item quantities and shipment charges."},
            {"name": "get_supplier_scorecards", "purpose": "Compare supplier lead times, on-time delivery, fill rates, shipment transit and rejected quantities."},
            {"name": "get_supply_chain_exceptions", "purpose": "Find delayed shipments, overdue ETAs and stale tracking updates."},
        ],
        "supply_chain": {
            "capabilities": ["supplier origins", "purchase orders", "inbound shipment tracking", "tracking event history", "goods receipts", "shipment charges", "supplier scorecards", "delay exceptions", "transit time", "OTIF and fill-rate metrics"],
            "carrier_tracking": "Manual tracking events in this development release; carrier API/EDI integrations are not connected.",
            "tenant_filter": "organization_id",
        },
        "knowledge_base": {"vector_store": "ChromaDB", "document_types": ["PDF", "TXT", "MD", "CSV"], "citations": "filename and page number", "tenant_filter": "organization_id"},
        "mcp": {"transport": "streamable-http", "url": "http://localhost:8001/mcp", "scope": "development demo organization configured in the MCP service"},
        "safety": [
            "Tools are bound to the organization supplied by the request dependency.",
            "Only predefined, read-only analytics tools are exposed; the model cannot submit arbitrary SQL.",
            "The local X-Organization-ID header is a development-only tenant selector, not production authentication.",
        ],
    }


@router.post("/agent/ask")
def ask_business_analyst(
    payload: AgentAskRequest,
    org_id: str = Depends(tenant_id),
):
    """Run a bounded, tenant-scoped AI investigation using read-only tools."""
    try:
        result = run_agent(
            question=payload.question.strip(),
            organization_id=org_id,
            max_tool_rounds=payload.max_tool_rounds,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AgentExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"organization_id": org_id, **result}


@router.post("/intelligence/analyse")
def two_agent_intelligence(
    payload: TwoAgentAnalysisRequest,
    org_id: str = Depends(tenant_id),
):
    """Run the deterministic Data Analyst stage, then grounded Business Analyst reasoning."""
    from profitpulse.agent.two_agent import run_two_agent_analysis

    try:
        return {
            "organization_id": org_id,
            **run_two_agent_analysis(
                question=payload.question.strip(),
                organization_id=org_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                max_tool_rounds=payload.max_tool_rounds,
            ),
        }
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AgentExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def organization_currency(conn, organization_id: str) -> str:
    row = conn.execute(
        "SELECT base_currency FROM organizations WHERE id=%s", (organization_id,)
    ).fetchone()
    return str(row["base_currency"]).strip() if row else "INR"


@router.get("/organizations/current")
def current_organization(org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        row = conn.execute(
            "SELECT id, legal_name, display_name, industry, base_currency FROM organizations WHERE id = %s",
            (org_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found in tenant context")
    return row


@router.get("/financial/summary")
def financial_summary(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date = Query(default=date(2026, 12, 31)),
    org_id: str = Depends(tenant_id),
):
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")
    with organization_connection(org_id) as conn:
        metrics = load_financial_summary(conn, org_id, start_date, end_date)
        currency = organization_currency(conn, org_id)
    return {
        "organization_id": org_id,
        "currency": currency,
        "period": {"start_date": str(start_date), "end_date": str(end_date)},
        "metrics": metrics,
    }


@router.get("/dashboard/summary")
def dashboard_summary(org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        financial = load_financial_summary(conn, org_id, date(2026, 1, 1), date(2026, 12, 31))
        currency = organization_currency(conn, org_id)
        counts = conn.execute(
            """SELECT
                (SELECT count(*) FROM customers) AS customers,
                (SELECT count(*) FROM products WHERE is_active) AS active_products,
                (SELECT count(*) FROM orders) AS orders,
                (SELECT count(*) FROM suppliers) AS suppliers"""
        ).fetchone()
    return {"organization_id": org_id, "currency": currency, "financial_metrics": financial, "business_counts": counts}


def _validate_period(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")


@router.get("/financial/balance-sheet")
def balance_sheet(
    as_of_date: date = Query(default=date(2026, 10, 31)),
    org_id: str = Depends(tenant_id),
):
    with organization_connection(org_id) as conn:
        statement = load_balance_sheet(conn, org_id, as_of_date)
        currency = organization_currency(conn, org_id)
    return {"organization_id": org_id, "currency": currency, "as_of_date": str(as_of_date),
            "statement": statement,
            "notes": [
                "Current fiscal-year earnings are included in equity because the starter ledger does not post year-end closing entries.",
                "Debt is not split into current and non-current maturities; current ratio and quick ratio are therefore not reported.",
                "Operating working-capital proxy excludes cash and borrowings and is not a substitute for a fully classified working-capital schedule.",
            ]}


@router.get("/financial/ratios")
def financial_ratios(
    start_date: date = Query(default=date(2026, 8, 1)),
    end_date: date = Query(default=date(2026, 10, 31)),
    org_id: str = Depends(tenant_id),
):
    _validate_period(start_date, end_date)
    with organization_connection(org_id) as conn:
        period_metrics = load_financial_summary(conn, org_id, start_date, end_date)
        opening = load_balance_sheet(conn, org_id, start_date.fromordinal(start_date.toordinal() - 1))
        closing = load_balance_sheet(conn, org_id, end_date)
        ratios = compute_financial_ratios(period_metrics, opening, closing)
        currency = organization_currency(conn, org_id)
    return {
        "organization_id": org_id,
        "currency": currency,
        "period": {"start_date": str(start_date), "end_date": str(end_date)},
        "ratios": {key: (float(value) if value is not None else None) for key, value in ratios.items()},
        "definitions": {
            "return_on_assets_pct": "Period PAT divided by average opening and closing total assets, multiplied by 100.",
            "return_on_equity_pct": "Period PAT divided by average opening and closing equity including current fiscal-year earnings, multiplied by 100.",
            "asset_turnover_x": "Period net revenue divided by average total assets.",
            "debt_to_equity_x": "Closing ledger debt divided by closing equity including current fiscal-year earnings.",
            "interest_coverage_x": "Period EBIT divided by period interest expense.",
        },
    }


@router.get("/financial/monthly-trend")
def monthly_financial_trend(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date = Query(default=date(2026, 12, 31)),
    org_id: str = Depends(tenant_id),
):
    _validate_period(start_date, end_date)
    with organization_connection(org_id) as conn:
        trend = load_monthly_financial_trend(conn, org_id, start_date, end_date)
        currency = organization_currency(conn, org_id)
    return {"organization_id": org_id, "currency": currency,
            "period": {"start_date": str(start_date), "end_date": str(end_date)},
            "months": trend}


@router.get("/financial/budget-variance")
def financial_budget_variance(
    period_start: date = Query(default=date(2026, 10, 1)),
    period_end: date = Query(default=date(2026, 10, 31)),
    org_id: str = Depends(tenant_id),
):
    _validate_period(period_start, period_end)
    with organization_connection(org_id) as conn:
        variances = load_budget_variance(conn, org_id, period_start, period_end)
        currency = organization_currency(conn, org_id)
    return {"organization_id": org_id, "currency": currency,
            "period": {"start_date": str(period_start), "end_date": str(period_end)},
            "variances": variances,
            "note": "Budget records are matched on exact start and end dates."}


@router.get("/analytics/product-performance")
def product_performance(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date = Query(default=date(2026, 12, 31)),
    limit: int = Query(default=20, ge=1, le=100),
    org_id: str = Depends(tenant_id),
):
    _validate_period(start_date, end_date)
    with organization_connection(org_id) as conn:
        products = load_product_performance(conn, org_id, start_date, end_date, limit)
        currency = organization_currency(conn, org_id)
    return {"organization_id": org_id, "currency": currency,
            "period": {"start_date": str(start_date), "end_date": str(end_date)},
            "products": products,
            "basis": "Delivered orders only; item line totals are used as net sales and exclude order-level tax/shipping."}


@router.get("/analytics/regional-performance")
def regional_performance(
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date = Query(default=date(2026, 12, 31)),
    org_id: str = Depends(tenant_id),
):
    _validate_period(start_date, end_date)
    with organization_connection(org_id) as conn:
        regions = load_regional_performance(conn, org_id, start_date, end_date)
        currency = organization_currency(conn, org_id)
    return {"organization_id": org_id, "currency": currency,
            "period": {"start_date": str(start_date), "end_date": str(end_date)},
            "regions": regions,
            "basis": "Delivered orders only; item line totals are used as net sales."}


@router.get("/analytics/inventory-health")
def inventory_health(
    as_of_date: date = Query(default=date(2026, 11, 1)),
    org_id: str = Depends(tenant_id),
):
    with organization_connection(org_id) as conn:
        inventory = load_inventory_health(conn, org_id, as_of_date)
        currency = organization_currency(conn, org_id)
    return {"organization_id": org_id, "currency": currency, "as_of_date": str(as_of_date),
            "inventory": inventory,
            "note": "Uses the latest available inventory snapshot on or before the requested date."}


@router.post("/knowledge/documents", status_code=201)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    org_id: str = Depends(tenant_id),
):
    """Index a PDF/TXT/Markdown/CSV document with tenant-scoped page/chunk metadata."""
    from pathlib import Path
    from profitpulse.rag.chunker import extract_document_pages
    from profitpulse.rag.store import KnowledgeStoreError, get_knowledge_store

    filename = Path(file.filename or "document.txt").name[:255]
    max_document_bytes = int(os.getenv("RAG_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    content = await file.read(max_document_bytes + 1)
    if len(content) > max_document_bytes:
        raise HTTPException(status_code=413, detail=f"Knowledge document exceeds the {max_document_bytes}-byte upload limit")
    try:
        pages = extract_document_pages(filename, content)
        result = get_knowledge_store().ingest(org_id, filename, pages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KnowledgeStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"organization_id": org_id, **result,
            "note": "Only selectable text is indexed. Scanned PDFs require OCR before ingestion."}


@router.post("/knowledge/search")
def search_knowledge_documents(
    payload: KnowledgeSearchRequest,
    org_id: str = Depends(tenant_id),
):
    """Retrieve tenant-scoped document passages and source/page citations."""
    from profitpulse.rag.store import KnowledgeStoreError, get_knowledge_store

    try:
        result = get_knowledge_store().search(org_id, payload.query, payload.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KnowledgeStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"organization_id": org_id, **result}


@router.get("/knowledge/documents")
def list_knowledge_documents(org_id: str = Depends(tenant_id)):
    from profitpulse.rag.store import KnowledgeStoreError, get_knowledge_store

    try:
        documents = get_knowledge_store().list_documents(org_id)
    except KnowledgeStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"organization_id": org_id, "documents": documents}


@router.delete("/knowledge/documents/{document_id}")
def delete_knowledge_document(document_id: UUID, org_id: str = Depends(tenant_id)):
    from profitpulse.rag.store import KnowledgeStoreError, get_knowledge_store

    try:
        deleted_chunks = get_knowledge_store().delete_document(org_id, str(document_id))
    except KnowledgeStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if deleted_chunks == 0:
        raise HTTPException(status_code=404, detail="Knowledge document not found for this organization")
    return {"organization_id": org_id, "document_id": str(document_id), "deleted_chunks": deleted_chunks}


@router.post("/imports/{entity}", status_code=201)
async def import_csv(
    entity: str,
    file: UploadFile = File(...),
    org_id: str = Depends(tenant_id),
):
    if entity not in {"customers", "products"}:
        raise HTTPException(status_code=400, detail="Supported entities: customers, products")
    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail=f"CSV exceeds {MAX_CSV_BYTES} byte limit")
    try:
        accepted, errors, total = parse_csv(content, entity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = (file.filename or f"{entity}.csv")[:255]
    with organization_connection(org_id) as conn:
        job = conn.execute(
            """INSERT INTO import_jobs (organization_id, entity_type, file_name, status, total_rows)
               VALUES (%s, %s, %s, 'processing', %s) RETURNING id""",
            (org_id, entity, filename, total),
        ).fetchone()
        job_id = str(job["id"])
        accepted_count = 0

        for row in accepted:
            source_row_number = row.pop("_row_number", 0)
            if entity == "customers":
                inserted = conn.execute(
                    """INSERT INTO customers
                       (organization_id, customer_code, name, email, phone, city, state, region, customer_type)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT DO NOTHING RETURNING id""",
                    (org_id, row["customer_code"], row["name"], row.get("email"), row.get("phone"),
                     row.get("city"), row.get("state"), row.get("region"), row.get("customer_type", "retail")),
                ).fetchone()
            else:
                inserted = conn.execute(
                    """INSERT INTO products
                       (organization_id, sku, name, category, unit_price, unit_cost, reorder_level, unit_of_measure)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT DO NOTHING RETURNING id""",
                    (org_id, row["sku"], row["name"], row["category"], row["unit_price"], row["unit_cost"],
                     row["reorder_level"], row.get("unit_of_measure", "unit")),
                ).fetchone()
            if inserted:
                accepted_count += 1
            else:
                errors.append({
                    "row_number": source_row_number,
                    "error_message": "Duplicate organization code/SKU or email",
                    "raw_row": row,
                })

        for error in errors:
            conn.execute(
                """INSERT INTO import_row_errors
                   (organization_id, import_job_id, row_number, error_message, raw_row)
                   VALUES (%s,%s,%s,%s,%s::jsonb)""",
                (org_id, job_id, error.get("row_number") or 0,
                 error["error_message"][:2000], json.dumps(error["raw_row"], default=str)),
            )

        rejected_count = len(errors)
        status = "completed_with_errors" if rejected_count else "completed"
        conn.execute(
            """UPDATE import_jobs SET accepted_rows=%s, rejected_rows=%s, status=%s, completed_at=now()
               WHERE organization_id=%s AND id=%s""",
            (accepted_count, rejected_count, status, org_id, job_id),
        )

    return {
        "import_job_id": job_id,
        "entity": entity,
        "total_rows": total,
        "accepted_rows": accepted_count,
        "rejected_rows": rejected_count,
        "status": status,
    }


@router.get("/imports/{job_id}")
def get_import_job(job_id: UUID, org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        job = conn.execute(
            """SELECT id, entity_type, file_name, status, total_rows, accepted_rows,
                      rejected_rows, created_at, completed_at
               FROM import_jobs WHERE organization_id=%s AND id=%s""",
            (org_id, str(job_id)),
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Import job not found")
        errors = conn.execute(
            """SELECT row_number, error_message, raw_row FROM import_row_errors
               WHERE organization_id=%s AND import_job_id=%s ORDER BY created_at""",
            (org_id, str(job_id)),
        ).fetchall()
    return {"job": job, "errors": errors}


# Supply Chain Intelligence -------------------------------------------------

@router.get("/supply-chain/overview")
def supply_chain_overview(org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        result = load_supply_chain_overview(conn, org_id)
        currency = organization_currency(conn, org_id)
    return {
    "organization_id": org_id,
    "currency": currency,
    **result
}


@router.get("/supply-chain/catalog")
def supply_chain_catalog(org_id: str = Depends(tenant_id)):
    """Return tenant-scoped active products and destination warehouses for PO/shipment forms."""
    with organization_connection(org_id) as conn:
        suppliers = conn.execute(
            "SELECT id,supplier_code,name,city,state FROM suppliers WHERE organization_id=%s ORDER BY name",
            (org_id,),
        ).fetchall()
        products = conn.execute(
            "SELECT id,sku,name,category,unit_of_measure,unit_cost FROM products WHERE organization_id=%s AND is_active=true ORDER BY name",
            (org_id,),
        ).fetchall()
        warehouses = conn.execute(
            "SELECT id,warehouse_code,name,city,state FROM warehouses WHERE organization_id=%s ORDER BY name",
            (org_id,),
        ).fetchall()
        currency = organization_currency(conn, org_id)
    return {"organization_id":org_id, "currency": currency,
            "suppliers":suppliers, "products":products, "warehouses":warehouses}


@router.get("/supply-chain/suppliers")
def supply_chain_suppliers(org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        suppliers = load_supplier_sites(conn, org_id)
    return {"organization_id": org_id, "suppliers": suppliers}


@router.post("/supply-chain/suppliers/{supplier_id}/sites", status_code=201)
def create_supplier_site(
    supplier_id: UUID,
    payload: SupplierSiteRequest,
    org_id: str = Depends(tenant_id),
):
    with organization_connection(org_id) as conn:
        supplier = conn.execute(
            "SELECT id FROM suppliers WHERE organization_id=%s AND id=%s",
            (org_id, str(supplier_id)),
        ).fetchone()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        if payload.is_primary:
            conn.execute(
                "UPDATE sc_supplier_sites SET is_primary=false WHERE organization_id=%s AND supplier_id=%s",
                (org_id, str(supplier_id)),
            )
        try:
            row = conn.execute(
                """INSERT INTO sc_supplier_sites(
                     organization_id,supplier_id,site_code,site_name,site_type,origin_city,origin_state,
                     origin_country,origin_country_code,origin_postal_code,origin_port,default_lead_time_days,
                     preferred_transport_mode,is_primary,notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id,site_code,site_name,origin_city,origin_state,origin_country,
                             origin_port,default_lead_time_days,preferred_transport_mode,is_primary""",
                (org_id,str(supplier_id),payload.site_code,payload.site_name,payload.site_type,
                 payload.origin_city,payload.origin_state,payload.origin_country,
                 payload.origin_country_code.upper() if payload.origin_country_code else None,
                 payload.origin_postal_code,payload.origin_port,payload.default_lead_time_days,
                 payload.preferred_transport_mode,payload.is_primary,payload.notes),
            ).fetchone()
            conn.execute(
                """INSERT INTO audit_events(organization_id,event_type,resource_type,resource_id,details)
                   VALUES (%s,'supply_chain.supplier_site_created','supplier_site',%s,%s::jsonb)""",
                (org_id,str(row["id"]),json.dumps({"supplier_id":str(supplier_id),"site_code":payload.site_code,"origin_city":payload.origin_city,"origin_country":payload.origin_country})),
            )
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise HTTPException(status_code=409, detail="Supplier site code already exists") from exc
            raise
    return {"organization_id": org_id, "supplier_id": str(supplier_id), "site": row}


@router.get("/supply-chain/purchase-orders")
def supply_chain_purchase_orders(
    status: str | None = Query(default=None, pattern="^(draft|sent|partially_received|received|cancelled)$"),
    limit: int = Query(default=50, ge=1, le=200),
    org_id: str = Depends(tenant_id),
):
    with organization_connection(org_id) as conn:
        rows = load_purchase_orders(conn, org_id, status, limit)
        currency = organization_currency(conn, org_id)
    return {"organization_id": org_id, "currency": currency, "purchase_orders": rows}


@router.post("/supply-chain/purchase-orders", status_code=201)
def create_supply_chain_purchase_order(
    payload: PurchaseOrderCreateRequest,
    org_id: str = Depends(tenant_id),
):
    if payload.expected_date and payload.expected_date < payload.order_date:
        raise HTTPException(status_code=422, detail="expected_date cannot be before order_date")
    with organization_connection(org_id) as conn:
        supplier = conn.execute(
            "SELECT id FROM suppliers WHERE organization_id=%s AND id=%s",
            (org_id,str(payload.supplier_id)),
        ).fetchone()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        product_ids = list({str(item.product_id) for item in payload.items})
        found = conn.execute(
            "SELECT id FROM products WHERE organization_id=%s AND id=ANY(%s::uuid[]) AND is_active=true",
            (org_id,product_ids),
        ).fetchall()
        if len(found) != len(product_ids):
            raise HTTPException(status_code=422, detail="One or more products are missing, inactive or outside this organization")
        try:
            po = conn.execute(
                """INSERT INTO purchase_orders(organization_id,supplier_id,po_number,order_date,expected_date,status,total_amount)
                   VALUES (%s,%s,%s,%s,%s,'draft',0) RETURNING id,po_number,status""",
                (org_id,str(payload.supplier_id),payload.po_number,payload.order_date,payload.expected_date),
            ).fetchone()
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise HTTPException(status_code=409, detail="Purchase order number already exists") from exc
            raise
        total = Decimal("0.00")
        for item in payload.items:
            line_total = (item.quantity_ordered * item.unit_cost).quantize(Decimal("0.01"))
            total += line_total
            conn.execute(
                """INSERT INTO purchase_order_items(organization_id,purchase_order_id,product_id,
                     quantity_ordered,quantity_received,unit_cost,line_total)
                   VALUES (%s,%s,%s,%s,0,%s,%s)""",
                (org_id,str(po["id"]),str(item.product_id),item.quantity_ordered,item.unit_cost,line_total),
            )
        conn.execute(
            "UPDATE purchase_orders SET total_amount=%s WHERE organization_id=%s AND id=%s",
            (total,org_id,str(po["id"])),
        )
        conn.execute(
            """INSERT INTO audit_events(organization_id,event_type,resource_type,resource_id,details)
               VALUES (%s,'supply_chain.purchase_order_created','purchase_order',%s,%s::jsonb)""",
            (org_id,str(po["id"]),json.dumps({"po_number":payload.po_number,"line_count":len(payload.items)})),
        )
    return {"organization_id": org_id, "purchase_order_id": str(po["id"]),
            "po_number": po["po_number"], "status": "draft", "total_amount": float(total), "currency": currency}


@router.post("/supply-chain/purchase-orders/{purchase_order_id}/send")
def send_supply_chain_purchase_order(purchase_order_id: UUID, org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        row = conn.execute(
            """UPDATE purchase_orders SET status='sent'
               WHERE organization_id=%s AND id=%s AND status='draft'
               RETURNING id,po_number,status,expected_date""",
            (org_id,str(purchase_order_id)),
        ).fetchone()
        if not row:
            existing = conn.execute(
                "SELECT status FROM purchase_orders WHERE organization_id=%s AND id=%s",
                (org_id,str(purchase_order_id)),
            ).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Purchase order not found")
            raise HTTPException(status_code=409, detail=f"Only draft purchase orders can be sent; current status is {existing['status']}")
        conn.execute(
            """INSERT INTO audit_events(organization_id,event_type,resource_type,resource_id,details)
               VALUES (%s,'supply_chain.purchase_order_sent','purchase_order',%s,'{}'::jsonb)""",
            (org_id,str(purchase_order_id)),
        )
    return {"organization_id": org_id, "purchase_order": row}


@router.get("/supply-chain/shipments")
def supply_chain_shipments(
    status: str | None = Query(default=None, pattern="^(planned|booked|picked_up|in_transit|at_origin_port|in_customs|at_destination_port|out_for_delivery|arrived_at_warehouse|delayed|exception|delivered|cancelled)$"),
    limit: int = Query(default=50, ge=1, le=200),
    org_id: str = Depends(tenant_id),
):
    with organization_connection(org_id) as conn:
        rows = load_shipments(conn, org_id, status, limit)
        currency = organization_currency(conn, org_id)
    return {"organization_id": org_id, "currency": currency, "shipments": rows,
            "tracking_note": "Tracking events are manually entered in this release; live carrier API/EDI connections are not configured."}


@router.post("/supply-chain/shipments", status_code=201)
def create_supply_chain_shipment(
    payload: ShipmentCreateRequest,
    org_id: str = Depends(tenant_id),
):
    with organization_connection(org_id) as conn:
        if not conn.execute(
            "SELECT id FROM suppliers WHERE organization_id=%s AND id=%s",
            (org_id,str(payload.supplier_id)),
        ).fetchone():
            raise HTTPException(status_code=404, detail="Supplier not found")
        warehouse = conn.execute(
            "SELECT id FROM warehouses WHERE organization_id=%s AND id=%s",
            (org_id,str(payload.destination_warehouse_id)),
        ).fetchone()
        if not warehouse:
            raise HTTPException(status_code=404, detail="Destination warehouse not found")
        site = None
        if payload.supplier_site_id:
            site = conn.execute(
                """SELECT * FROM sc_supplier_sites WHERE organization_id=%s AND id=%s
                   AND supplier_id=%s AND is_active=true""",
                (org_id,str(payload.supplier_site_id),str(payload.supplier_id)),
            ).fetchone()
            if not site:
                raise HTTPException(status_code=404, detail="Active supplier origin site not found")
        po_ids = list(dict.fromkeys(str(item) for item in payload.purchase_order_ids))
        purchase_orders = conn.execute(
            """SELECT id,supplier_id,status FROM purchase_orders
               WHERE organization_id=%s AND id=ANY(%s::uuid[])""",
            (org_id,po_ids),
        ).fetchall()
        if len(purchase_orders) != len(po_ids):
            raise HTTPException(status_code=404, detail="One or more purchase orders were not found in this organization")
        for po in purchase_orders:
            if str(po["supplier_id"]) != str(payload.supplier_id):
                raise HTTPException(status_code=422, detail="A shipment can consolidate purchase orders from only one supplier")
            if po["status"] not in ("sent","partially_received"):
                raise HTTPException(status_code=409, detail=f"Purchase order {po['id']} must be sent or partially received before dispatch")
        po_items = conn.execute(
            """SELECT poi.id,poi.purchase_order_id,poi.quantity_ordered,poi.quantity_received,
                      COALESCE(sum(greatest(si.quantity_shipped-si.quantity_received,0)) FILTER (WHERE sh.status<>'cancelled'),0) AS already_shipped
               FROM purchase_order_items poi
               LEFT JOIN sc_shipment_items si ON si.organization_id=poi.organization_id
                    AND si.purchase_order_item_id=poi.id
               LEFT JOIN sc_inbound_shipments sh ON sh.organization_id=si.organization_id AND sh.id=si.shipment_id
               WHERE poi.organization_id=%s AND poi.purchase_order_id=ANY(%s::uuid[])
               GROUP BY poi.id,poi.purchase_order_id,poi.quantity_ordered,poi.quantity_received""",
            (org_id,po_ids),
        ).fetchall()
        available = {str(row["id"]): row for row in po_items}
        requested = payload.items or [
            ShipmentLineRequest(purchase_order_item_id=UUID(str(row["id"])),
                quantity_shipped=Decimal(str(row["quantity_ordered"]))-Decimal(str(row["quantity_received"]))-Decimal(str(row["already_shipped"])))
            for row in po_items
            if Decimal(str(row["quantity_ordered"]))-Decimal(str(row["quantity_received"]))-Decimal(str(row["already_shipped"])) > 0
        ]
        if not requested:
            raise HTTPException(status_code=409, detail="No outstanding purchase-order quantity is available to ship")
        for line in requested:
            key = str(line.purchase_order_item_id)
            if key not in available:
                raise HTTPException(status_code=422, detail="Shipment line references an item outside the selected purchase orders")
            row = available[key]
            outstanding = Decimal(str(row["quantity_ordered"]))-Decimal(str(row["quantity_received"]))-Decimal(str(row["already_shipped"]))
            if line.quantity_shipped > outstanding:
                raise HTTPException(status_code=422, detail=f"Shipment quantity exceeds outstanding quantity for purchase order item {key}")
        currency = organization_currency(conn, org_id)
        origin_city = (site["origin_city"] if site else payload.origin_city)
        origin_state = (site["origin_state"] if site else payload.origin_state)
        origin_country = (site["origin_country"] if site else payload.origin_country)
        origin_country_code = (site["origin_country_code"] if site else payload.origin_country_code)
        origin_port = (payload.origin_port or (site["origin_port"] if site else None))
        if not origin_city or not origin_country:
            raise HTTPException(status_code=422, detail="Provide origin_city and origin_country, or select a supplier origin site")
        try:
            shipment = conn.execute(
                """INSERT INTO sc_inbound_shipments(
                     organization_id,shipment_number,supplier_id,supplier_site_id,destination_warehouse_id,
                     origin_city,origin_state,origin_country,origin_country_code,origin_port,destination_port,
                     carrier_name,carrier_service,tracking_number,transport_mode,incoterm,status,
                     planned_departure_at,promised_arrival_at,current_eta_at,currency,notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'booked',%s,%s,%s,%s,%s)
                   RETURNING id,shipment_number,status""",
                (org_id,payload.shipment_number,str(payload.supplier_id),str(payload.supplier_site_id) if payload.supplier_site_id else None,
                 str(payload.destination_warehouse_id),origin_city,origin_state,origin_country,
                 origin_country_code.upper() if origin_country_code else None,
                 origin_port,payload.destination_port,payload.carrier_name,payload.carrier_service,
                 payload.tracking_number,payload.transport_mode,payload.incoterm,payload.planned_departure_at,
                 payload.promised_arrival_at,payload.current_eta_at or payload.promised_arrival_at,currency,payload.notes),
            ).fetchone()
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise HTTPException(status_code=409, detail="Shipment number already exists") from exc
            raise
        shipment_id = str(shipment["id"])
        for po_id in po_ids:
            conn.execute(
                "INSERT INTO sc_shipment_purchase_orders(organization_id,shipment_id,purchase_order_id) VALUES (%s,%s,%s)",
                (org_id,shipment_id,po_id),
            )
        for line in requested:
            row = available[str(line.purchase_order_item_id)]
            conn.execute(
                """INSERT INTO sc_shipment_items(organization_id,shipment_id,purchase_order_id,purchase_order_item_id,quantity_shipped)
                   VALUES (%s,%s,%s,%s,%s)""",
                (org_id,shipment_id,str(row["purchase_order_id"]),str(line.purchase_order_item_id),line.quantity_shipped),
            )
        created_at = datetime.now(timezone.utc)
        conn.execute(
            """INSERT INTO sc_shipment_events(organization_id,shipment_id,event_code,status_after,location_name,
                 city,state,country,occurred_at,notes,source)
               VALUES (%s,%s,'booked','booked',%s,%s,%s,%s,%s,%s,'manual')""",
            (org_id,shipment_id,origin_city,origin_city,origin_state,origin_country,created_at,
             payload.notes or "Shipment created in ProfitPulse."),
        )
        conn.execute(
            """INSERT INTO audit_events(organization_id,event_type,resource_type,resource_id,details)
               VALUES (%s,'supply_chain.shipment_created','inbound_shipment',%s,%s::jsonb)""",
            (org_id,shipment_id,json.dumps({"shipment_number":payload.shipment_number,"purchase_order_ids":po_ids})),
        )
    return {"organization_id": org_id, "shipment_id": shipment_id,
            "shipment_number": shipment["shipment_number"], "status": shipment["status"],
            "linked_purchase_orders": len(po_ids), "shipment_lines": len(requested)}


@router.get("/supply-chain/shipments/{shipment_id}/timeline")
def supply_chain_shipment_timeline(shipment_id: UUID, org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        result = load_shipment_timeline(conn, org_id, str(shipment_id))
    if not result:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return {"organization_id": org_id, **result}


@router.post("/supply-chain/shipments/{shipment_id}/events", status_code=201)
def add_supply_chain_tracking_event(
    shipment_id: UUID,
    payload: ShipmentEventRequest,
    org_id: str = Depends(tenant_id),
):
    event_time = payload.occurred_at or datetime.now(timezone.utc)
    event_status = {
        "booked":"booked", "picked_up":"picked_up", "departed_origin":"in_transit",
        "in_transit":"in_transit", "arrived_origin_port":"at_origin_port",
        "customs_started":"in_customs", "customs_cleared":"in_transit",
        "departed_port":"in_transit", "arrived_destination_port":"at_destination_port",
        "out_for_delivery":"out_for_delivery", "arrived_warehouse":"arrived_at_warehouse",
        "delayed":"delayed", "exception":"exception",
    }.get(payload.event_code)
    if payload.event_code in ("picked_up", "departed_origin") and payload.current_eta_at and payload.current_eta_at < event_time:
        raise HTTPException(status_code=422, detail="current_eta_at cannot be before the departure event time")
    with organization_connection(org_id) as conn:
        shipment = conn.execute(
            "SELECT id,status,actual_departure_at FROM sc_inbound_shipments WHERE organization_id=%s AND id=%s",
            (org_id,str(shipment_id)),
        ).fetchone()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        if shipment["status"] in ("delivered","cancelled"):
            raise HTTPException(status_code=409, detail="Delivered or cancelled shipments cannot receive further tracking updates")
        if payload.event_code == "arrived_warehouse" and shipment["actual_departure_at"] and event_time < shipment["actual_departure_at"]:
            raise HTTPException(status_code=422, detail="Warehouse arrival cannot be before actual departure")
        try:
            event = conn.execute(
                """INSERT INTO sc_shipment_events(organization_id,shipment_id,event_code,status_after,
                     location_name,city,state,country,occurred_at,notes,source)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'manual')
                   RETURNING id,event_code,status_after,occurred_at""",
                (org_id,str(shipment_id),payload.event_code,event_status,payload.location_name,
                 payload.city,payload.state,payload.country,event_time,payload.notes),
            ).fetchone()
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise HTTPException(status_code=409, detail="An identical event already exists for this shipment and timestamp") from exc
            raise
        if payload.current_eta_at is not None:
            if shipment["actual_departure_at"] and payload.current_eta_at < shipment["actual_departure_at"]:
                raise HTTPException(status_code=422, detail="current_eta_at cannot be before actual departure")
            conn.execute(
                "UPDATE sc_inbound_shipments SET current_eta_at=%s,updated_at=now() WHERE organization_id=%s AND id=%s",
                (payload.current_eta_at,org_id,str(shipment_id)),
            )
        if event_status in ("delivered", "arrived_at_warehouse"):
            conn.execute(
                "UPDATE sc_inbound_shipments SET status=%s,actual_arrival_at=COALESCE(actual_arrival_at,%s),updated_at=now() WHERE organization_id=%s AND id=%s",
                (event_status,event_time,org_id,str(shipment_id)),
            )
        elif event_status:
            if payload.event_code in ("picked_up", "departed_origin"):
                conn.execute(
                    "UPDATE sc_inbound_shipments SET status=%s,actual_departure_at=COALESCE(actual_departure_at,%s),updated_at=now() WHERE organization_id=%s AND id=%s",
                    (event_status,event_time,org_id,str(shipment_id)),
                )
            else:
                conn.execute(
                    "UPDATE sc_inbound_shipments SET status=%s,updated_at=now() WHERE organization_id=%s AND id=%s",
                    (event_status,org_id,str(shipment_id)),
                )
        elif payload.current_eta_at is None:
            conn.execute("UPDATE sc_inbound_shipments SET updated_at=now() WHERE organization_id=%s AND id=%s",
                         (org_id,str(shipment_id)))
        conn.execute(
            """INSERT INTO audit_events(organization_id,event_type,resource_type,resource_id,details)
               VALUES (%s,'supply_chain.tracking_event_added','inbound_shipment',%s,%s::jsonb)""",
            (org_id,str(shipment_id),json.dumps({"event_code":payload.event_code,"occurred_at":event_time.isoformat()})),
        )
    return {"organization_id":org_id,"shipment_id":str(shipment_id),"event":event}


@router.post("/supply-chain/shipments/{shipment_id}/charges", status_code=201)
def add_supply_chain_shipment_charge(
    shipment_id: UUID,
    payload: ShipmentCostRequest,
    org_id: str = Depends(tenant_id),
):
    with organization_connection(org_id) as conn:
        shipment = conn.execute(
            "SELECT id,currency FROM sc_inbound_shipments WHERE organization_id=%s AND id=%s",
            (org_id,str(shipment_id)),
        ).fetchone()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        charge = conn.execute(
            """INSERT INTO sc_shipment_costs(organization_id,shipment_id,cost_type,description,amount,currency,charge_date,reference)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,cost_type,amount,currency,charge_date""",
            (org_id,str(shipment_id),payload.cost_type,payload.description,payload.amount,
             shipment["currency"],payload.charge_date,payload.reference),
        ).fetchone()
        conn.execute(
            """INSERT INTO audit_events(organization_id,event_type,resource_type,resource_id,details)
               VALUES (%s,'supply_chain.shipment_charge_added','inbound_shipment',%s,%s::jsonb)""",
            (org_id,str(shipment_id),json.dumps({"charge_id":str(charge["id"]),"cost_type":payload.cost_type,"amount":str(payload.amount),"currency":str(shipment["currency"])})),
        )
    return {"organization_id":org_id,"shipment_id":str(shipment_id),"charge":charge,
            "note":"Charges are stored in the shipment's currency. Cross-currency conversion is not performed."}


@router.post("/supply-chain/shipments/{shipment_id}/receipts", status_code=201)
def receive_supply_chain_goods(
    shipment_id: UUID,
    payload: GoodsReceiptRequest,
    org_id: str = Depends(tenant_id),
):
    for line in payload.items:
        if line.quantity_accepted + line.quantity_rejected != line.quantity_received:
            raise HTTPException(status_code=422, detail="For each receipt line, accepted plus rejected must equal received")
    with organization_connection(org_id) as conn:
        shipment = conn.execute(
            """SELECT id,status,destination_warehouse_id FROM sc_inbound_shipments
               WHERE organization_id=%s AND id=%s""",
            (org_id,str(shipment_id)),
        ).fetchone()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        if shipment["status"] != "arrived_at_warehouse":
            raise HTTPException(status_code=409, detail="Record an arrived_warehouse tracking milestone before posting a goods receipt")
        # Inventory snapshots are point-in-time balances. Receipts before the latest
        # snapshot cannot safely be added as post-snapshot movements; require a new snapshot.
        receipt_date = payload.received_at.date()
        line_records = []
        for line in payload.items:
            record = conn.execute(
                """SELECT si.id,si.purchase_order_id,si.purchase_order_item_id,si.quantity_shipped,si.quantity_received,
                          poi.quantity_ordered,poi.quantity_received AS po_quantity_received,poi.unit_cost,
                          (SELECT max(snap.snapshot_date) FROM inventory_snapshots snap
                            WHERE snap.organization_id=si.organization_id AND snap.product_id=poi.product_id
                              AND snap.warehouse_id=%s) AS latest_snapshot_date
                   FROM sc_shipment_items si
                   JOIN purchase_order_items poi ON poi.organization_id=si.organization_id
                        AND poi.purchase_order_id=si.purchase_order_id AND poi.id=si.purchase_order_item_id
                   WHERE si.organization_id=%s AND si.shipment_id=%s AND si.id=%s""",
                (str(shipment["destination_warehouse_id"]),org_id,str(shipment_id),str(line.shipment_item_id)),
            ).fetchone()
            if not record:
                raise HTTPException(status_code=404, detail=f"Shipment item {line.shipment_item_id} not found")
            if record["latest_snapshot_date"] and receipt_date <= record["latest_snapshot_date"]:
                raise HTTPException(status_code=409, detail="Receipt date is earlier than the latest inventory snapshot; create a corrected stock snapshot first")
            remaining_shipment = Decimal(str(record["quantity_shipped"]))-Decimal(str(record["quantity_received"]))
            remaining_po = Decimal(str(record["quantity_ordered"]))-Decimal(str(record["po_quantity_received"]))
            if line.quantity_received > min(remaining_shipment,remaining_po):
                raise HTTPException(status_code=422, detail="Receipt quantity exceeds the outstanding shipped or purchase-order quantity")
            line_records.append((line,record))
        receipt = conn.execute(
            """INSERT INTO sc_goods_receipts(organization_id,shipment_id,warehouse_id,receipt_number,received_at,inspection_status,notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id,receipt_number,received_at,inspection_status""",
            (org_id,str(shipment_id),str(shipment["destination_warehouse_id"]),payload.receipt_number,
             payload.received_at,payload.inspection_status,payload.notes),
        ).fetchone()
        received_total = Decimal("0")
        accepted_total = Decimal("0")
        rejected_total = Decimal("0")
        affected_pos = set()
        for line,record in line_records:
            conn.execute(
                """INSERT INTO sc_goods_receipt_items(organization_id,goods_receipt_id,shipment_item_id,
                     quantity_received,quantity_accepted,quantity_rejected,inspection_notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (org_id,str(receipt["id"]),str(line.shipment_item_id),line.quantity_received,
                 line.quantity_accepted,line.quantity_rejected,line.inspection_notes),
            )
            conn.execute(
                "UPDATE sc_shipment_items SET quantity_received=quantity_received+%s WHERE organization_id=%s AND id=%s",
                (line.quantity_received,org_id,str(line.shipment_item_id)),
            )
            conn.execute(
                "UPDATE purchase_order_items SET quantity_received=quantity_received+%s WHERE organization_id=%s AND id=%s",
                (line.quantity_accepted,org_id,str(record["purchase_order_item_id"])),
            )
            if line.quantity_accepted > 0:
                conn.execute(
                    """INSERT INTO inventory_movements(organization_id,product_id,warehouse_id,movement_date,
                         movement_type,quantity_delta,unit_cost,reference)
                       SELECT %s,poi.product_id,%s,%s,'purchase',%s,poi.unit_cost,%s
                       FROM purchase_order_items poi WHERE poi.organization_id=%s AND poi.id=%s""",
                    (org_id,str(shipment["destination_warehouse_id"]),receipt_date,line.quantity_accepted,
                     payload.receipt_number,org_id,str(record["purchase_order_item_id"])),
                )
            affected_pos.add(str(record["purchase_order_id"]))
            received_total += line.quantity_received
            accepted_total += line.quantity_accepted
            rejected_total += line.quantity_rejected
        # Update each PO from its actual received quantities.
        for po_id in affected_pos:
            quantities = conn.execute(
                """SELECT count(*) AS line_count,
                          count(*) FILTER (WHERE quantity_received >= quantity_ordered) AS complete_lines
                   FROM purchase_order_items WHERE organization_id=%s AND purchase_order_id=%s""",
                (org_id,po_id),
            ).fetchone()
            if quantities["line_count"] and quantities["complete_lines"] == quantities["line_count"]:
                conn.execute(
                    """UPDATE purchase_orders SET status='received',received_date=%s
                       WHERE organization_id=%s AND id=%s""",
                    (receipt_date,org_id,po_id),
                )
            else:
                conn.execute(
                    "UPDATE purchase_orders SET status='partially_received' WHERE organization_id=%s AND id=%s",
                    (org_id,po_id),
                )
        shipment_qty = conn.execute(
            """SELECT count(*) AS line_count,count(*) FILTER (WHERE quantity_received>=quantity_shipped) AS complete_lines
               FROM sc_shipment_items WHERE organization_id=%s AND shipment_id=%s""",
            (org_id,str(shipment_id)),
        ).fetchone()
        fully_received = bool(shipment_qty["line_count"] and shipment_qty["line_count"] == shipment_qty["complete_lines"])
        new_status = "delivered" if fully_received else "arrived_at_warehouse"
        if fully_received:
            conn.execute(
                "UPDATE sc_inbound_shipments SET status='delivered',actual_arrival_at=COALESCE(actual_arrival_at,%s),updated_at=now() WHERE organization_id=%s AND id=%s",
                (payload.received_at,org_id,str(shipment_id)),
            )
        else:
            conn.execute(
                "UPDATE sc_inbound_shipments SET status=%s,actual_arrival_at=COALESCE(actual_arrival_at,%s),updated_at=now() WHERE organization_id=%s AND id=%s",
                (new_status,payload.received_at,org_id,str(shipment_id)),
            )
        conn.execute(
            """INSERT INTO sc_shipment_events(organization_id,shipment_id,event_code,status_after,
                 location_name,occurred_at,notes,source)
               VALUES (%s,%s,'goods_received',%s,'Destination warehouse',%s,%s,'system')""",
            (org_id,str(shipment_id),new_status,payload.received_at,payload.notes or "Goods receipt posted."),
        )
        conn.execute(
            """INSERT INTO audit_events(organization_id,event_type,resource_type,resource_id,details)
               VALUES (%s,'supply_chain.goods_received','inbound_shipment',%s,%s::jsonb)""",
            (org_id,str(shipment_id),json.dumps({"receipt_number":payload.receipt_number,
                "quantity_received":str(received_total),"quantity_accepted":str(accepted_total),
                "quantity_rejected":str(rejected_total)})),
        )
    return {"organization_id":org_id,"shipment_id":str(shipment_id),"receipt":receipt,
            "quantity_received":float(received_total),"quantity_accepted":float(accepted_total),
            "quantity_rejected":float(rejected_total),"shipment_status":new_status,
            "inventory_note":"Accepted quantities were posted to inventory_movements. Inventory Health adds movements after the latest stock snapshot."}



@router.get("/supply-chain/supplier-scorecards")
def supply_chain_supplier_scorecards(org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        scorecards = load_supplier_scorecards(conn, org_id)
        currency = organization_currency(conn, org_id)

    return {
        "organization_id": org_id,
        "currency": currency,
        "scorecards": scorecards,
        "definitions": {
            "purchase_order_count":
                "Total non-cancelled purchase orders.",

            "open_po_count":
                "Purchase orders currently sent or partially received.",

            "completed_po_count":
                "Purchase orders with received status and recorded received_date.",

            "on_time_po_pct":
                "Percentage of completed purchase orders received on or before expected_date.",

            "otif_pct":
                "Percentage of completed purchase orders received on time and in full.",

            "fill_rate_pct":
                "Overall received quantity divided by ordered quantity across all non-cancelled purchase orders.",

            "completed_po_fill_rate_pct":
                "Received quantity divided by ordered quantity for completed purchase orders only.",

            "outstanding_quantity":
                "Total unreceived quantity on open purchase orders.",

            "avg_procurement_lead_days":
                "Average calendar days from purchase order date to received_date.",

            "shipment_count":
                "Total non-cancelled shipments.",

            "completed_shipments":
                "Shipments with actual departure and arrival timestamps.",

            "on_time_shipment_pct":
                "Percentage of completed shipments arriving on or before promised arrival date.",

            "avg_transit_days":
                "Average days between actual departure and actual arrival.",

            "rejected_quantity":
                "Total rejected quantity recorded in goods receipts.",

            "receipt_quantity":
                "Total physically received quantity recorded in goods receipts.",

            "rejected_quantity_pct":
                "Rejected quantity divided by physically received quantity. Null when no receipt quantity exists.",

            "open_po_value":
                "Outstanding goods value calculated from unreceived quantities multiplied by unit costs."
        }
    }



@router.get("/supply-chain/exceptions")
def supply_chain_exceptions(org_id: str = Depends(tenant_id)):
    with organization_connection(org_id) as conn:
        exceptions = load_supply_chain_exceptions(conn, org_id)
    return {"organization_id":org_id,"exceptions":exceptions,
            "rules": ["Delayed or exception status", "Current ETA is in the past", "No tracking event for more than 72 hours"]}
