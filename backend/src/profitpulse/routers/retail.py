"""Multi-store clothing retail analytics and reporting endpoints.

V1 uses deterministic, auditable calculations for store Data Analyst and
Business Analyst workflows. The headquarters workflow consolidates reports.
No operational actions are executed.
"""
import csv
import io
import os
import smtplib
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from profitpulse.db import organization_connection

router = APIRouter(prefix="/api/v1/retail", tags=["multi-store retail"])


def retail_tenant_id(x_organization_id: UUID = Header(..., alias="X-Organization-ID")) -> str:
    return str(x_organization_id)


class StoreCreate(BaseModel):
    store_code: str = Field(min_length=2, max_length=40)
    store_name: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=100)
    monthly_revenue_threshold: Decimal = Field(default=Decimal("0"), ge=0)


class EmailRequest(BaseModel):
    recipient: str = Field(min_length=5, max_length=254)


def _decimal(value: str, field: str, row_number: int) -> Decimal:
    try:
        number = Decimal(value.strip())
        if not number.is_finite() or number < 0:
            raise InvalidOperation
        return number
    except (InvalidOperation, AttributeError):
        raise HTTPException(422, f"Invalid non-negative number in '{field}' at CSV row {row_number}") from None


def _csv_rows(raw: bytes, required: set[str]):
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        headers = {str(h).strip().lower() for h in (reader.fieldnames or [])}
        missing = required - headers
        if missing:
            raise HTTPException(422, f"CSV is missing required columns: {', '.join(sorted(missing))}")
        rows = []
        for row_number, raw_row in enumerate(reader, start=2):
            row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw_row.items()}
            if any(row.values()):
                rows.append((row_number, row))
        if not rows:
            raise HTTPException(422, "CSV contains a header but no data rows")
        if len(rows) > 50000:
            raise HTTPException(413, "A single upload is limited to 50,000 rows")
        return rows
    except UnicodeDecodeError:
        raise HTTPException(422, "Upload must be a UTF-8 CSV file") from None


def _store_or_404(conn, org_id: str, store_id: UUID):
    row = conn.execute(
        "SELECT id, store_code, store_name, city, monthly_revenue_threshold FROM retail_stores WHERE organization_id=%s AND id=%s",
        (org_id, str(store_id)),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Store not found")
    return row


@router.get("/stores")
def list_stores(org_id: str = Depends(retail_tenant_id)):
    with organization_connection(org_id) as conn:
        rows = conn.execute(
            """SELECT s.id, s.store_code, s.store_name, s.city, s.monthly_revenue_threshold,
                      (SELECT COUNT(*) FROM retail_sales x WHERE x.organization_id=s.organization_id AND x.store_id=s.id) AS sales_rows,
                      (SELECT MAX(snapshot_date) FROM retail_inventory_snapshots i WHERE i.organization_id=s.organization_id AND i.store_id=s.id) AS latest_inventory_date
               FROM retail_stores s WHERE s.organization_id=%s ORDER BY s.store_code""",
            (org_id,),
        ).fetchall()
    return {"stores": rows}


@router.post("/stores")
def create_store(payload: StoreCreate, org_id: str = Depends(retail_tenant_id)):
    with organization_connection(org_id) as conn:
        try:
            row = conn.execute(
                """INSERT INTO retail_stores (organization_id, store_code, store_name, city, monthly_revenue_threshold)
                   VALUES (%s,%s,%s,%s,%s)
                   RETURNING id, store_code, store_name, city, monthly_revenue_threshold""",
                (org_id, payload.store_code.strip().upper(), payload.store_name.strip(), payload.city.strip(), payload.monthly_revenue_threshold),
            ).fetchone()
        except Exception as exc:
            if "unique" in str(exc).lower():
                raise HTTPException(409, "A store with this code already exists") from exc
            raise
    return {"store": row}


@router.post("/stores/{store_id}/upload-sales")
async def upload_sales(store_id: UUID, file: UploadFile = File(...), org_id: str = Depends(retail_tenant_id)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, "Please upload a .csv sales file")
    raw = await file.read(10_000_001)
    if len(raw) > 10_000_000:
        raise HTTPException(413, "Maximum upload size is 10 MB")
    rows = _csv_rows(raw, {"sale_date", "sku", "product_name", "quantity", "unit_price", "unit_cost"})
    with organization_connection(org_id) as conn:
        _store_or_404(conn, org_id, store_id)
        batch = conn.execute(
            """INSERT INTO retail_import_batches (organization_id,store_id,import_type,file_name,row_count)
               VALUES (%s,%s,'sales',%s,%s) RETURNING id""",
            (org_id, str(store_id), file.filename, len(rows)),
        ).fetchone()["id"]
        for row_number, row in rows:
            try:
                sale_date = date.fromisoformat(row["sale_date"])
                if not row["sku"] or not row["product_name"]:
                    raise ValueError
            except ValueError:
                raise HTTPException(422, f"Invalid sale_date, SKU or product_name at CSV row {row_number}") from None
            conn.execute(
                """INSERT INTO retail_sales
                   (organization_id,store_id,import_batch_id,row_number,sale_date,sku,product_name,category,quantity,unit_price,unit_cost)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (org_id, str(store_id), str(batch), row_number, sale_date, row["sku"], row["product_name"],
                 row.get("category") or None, _decimal(row["quantity"], "quantity", row_number),
                 _decimal(row["unit_price"], "unit_price", row_number), _decimal(row["unit_cost"], "unit_cost", row_number)),
            )
    return {"status": "completed", "store_id": str(store_id), "batch_id": str(batch), "accepted_rows": len(rows), "file_name": file.filename}


@router.post("/stores/{store_id}/upload-inventory")
async def upload_inventory(store_id: UUID, file: UploadFile = File(...), org_id: str = Depends(retail_tenant_id)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, "Please upload a .csv inventory file")
    raw = await file.read(10_000_001)
    if len(raw) > 10_000_000:
        raise HTTPException(413, "Maximum upload size is 10 MB")
    rows = _csv_rows(raw, {"snapshot_date", "sku", "product_name", "stock_on_hand", "reorder_level", "unit_cost"})
    with organization_connection(org_id) as conn:
        _store_or_404(conn, org_id, store_id)
        for row_number, row in rows:
            try:
                snapshot_date = date.fromisoformat(row["snapshot_date"])
                if not row["sku"] or not row["product_name"]:
                    raise ValueError
            except ValueError:
                raise HTTPException(422, f"Invalid snapshot_date, SKU or product_name at CSV row {row_number}") from None
            conn.execute(
                """INSERT INTO retail_inventory_snapshots
                   (organization_id,store_id,snapshot_date,sku,product_name,category,stock_on_hand,reorder_level,unit_cost)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (organization_id,store_id,snapshot_date,sku) DO UPDATE SET
                     product_name=EXCLUDED.product_name, category=EXCLUDED.category,
                     stock_on_hand=EXCLUDED.stock_on_hand, reorder_level=EXCLUDED.reorder_level,
                     unit_cost=EXCLUDED.unit_cost""",
                (org_id, str(store_id), snapshot_date, row["sku"], row["product_name"], row.get("category") or None,
                 _decimal(row["stock_on_hand"], "stock_on_hand", row_number),
                 _decimal(row["reorder_level"], "reorder_level", row_number),
                 _decimal(row["unit_cost"], "unit_cost", row_number)),
            )
    return {"status": "completed", "store_id": str(store_id), "accepted_rows": len(rows), "file_name": file.filename}


def _store_report(conn, org_id: str, store, start_date: date | None = None, end_date: date | None = None):
    store_id = str(store["id"])
    sales = conn.execute(
        """SELECT COALESCE(SUM(quantity*unit_price),0) AS revenue,
                  COALESCE(SUM(quantity*unit_cost),0) AS cogs,
                  COALESCE(SUM(quantity),0) AS units_sold,
                  COUNT(*) AS line_count
           FROM retail_sales WHERE organization_id=%s AND store_id=%s
             AND (%s IS NULL OR sale_date >= %s) AND (%s IS NULL OR sale_date <= %s)""",
        (org_id, store_id, start_date, start_date, end_date, end_date),
    ).fetchone()
    inventory = conn.execute(
        """SELECT COUNT(*) FILTER (WHERE stock_on_hand <= reorder_level) AS low_stock_skus,
                  COUNT(*) AS sku_count, COALESCE(SUM(stock_on_hand*unit_cost),0) AS stock_value
           FROM retail_inventory_snapshots
           WHERE organization_id=%s AND store_id=%s
             AND snapshot_date=(SELECT MAX(snapshot_date) FROM retail_inventory_snapshots
                                WHERE organization_id=%s AND store_id=%s)""",
        (org_id, store_id, org_id, store_id),
    ).fetchone()
    top_products = conn.execute(
        """SELECT sku, product_name, SUM(quantity) AS units_sold,
                  SUM(quantity*unit_price) AS revenue,
                  SUM(quantity*(unit_price-unit_cost)) AS gross_profit
           FROM retail_sales WHERE organization_id=%s AND store_id=%s
             AND (%s IS NULL OR sale_date >= %s) AND (%s IS NULL OR sale_date <= %s)
           GROUP BY sku,product_name ORDER BY revenue DESC LIMIT 5""",
        (org_id, store_id, start_date, start_date, end_date, end_date),
    ).fetchall()
    revenue = Decimal(str(sales["revenue"] or 0))
    cogs = Decimal(str(sales["cogs"] or 0))
    gross_profit = revenue - cogs
    margin = float((gross_profit / revenue * 100) if revenue else 0)
    low_stock = int(inventory["low_stock_skus"] or 0)
    sku_count = int(inventory["sku_count"] or 0)
    data_analyst = {
        "agent": "Store Data Analyst Agent",
        "revenue": float(revenue), "cogs": float(cogs), "gross_profit": float(gross_profit),
        "gross_margin_pct": round(margin, 2), "units_sold": float(sales["units_sold"] or 0),
        "sales_lines": int(sales["line_count"] or 0), "low_stock_skus": low_stock,
        "tracked_skus": sku_count, "stock_value": float(inventory["stock_value"] or 0),
        "top_products": [dict(row) for row in top_products],
    }
    business_analyst = {
        "agent": "Store Business Analyst Agent",
        "findings": [
            f"Gross margin is {margin:.1f}% based on uploaded sales and unit costs.",
            f"{low_stock} of {sku_count} tracked SKUs are at or below their reorder level.",
            f"Recorded revenue is INR {float(revenue):,.0f} across {int(sales['line_count'] or 0)} uploaded sales lines.",
        ],
        "recommendations": (
            ["Review replenishment for the SKUs at or below reorder level."] if low_stock else
            ["No low-stock SKU was detected in the latest uploaded inventory snapshot."]
        ),
        "data_quality_note": "This is gross profit (sales less product cost), not net profit. Rent, salaries, tax and other operating expenses are excluded unless separately provided.",
    }
    return {
        "store": {"id": store_id, "code": store["store_code"], "name": store["store_name"], "city": store["city"]},
        "data_analyst": data_analyst, "business_analyst": business_analyst,
    }


@router.get("/stores/{store_id}/report")
def get_store_report(store_id: UUID, start_date: date | None = Query(default=None), end_date: date | None = Query(default=None), org_id: str = Depends(retail_tenant_id)):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be on or before end_date")
    with organization_connection(org_id) as conn:
        store = _store_or_404(conn, org_id, store_id)
        return _store_report(conn, org_id, store, start_date, end_date)


@router.get("/headquarters/report")
def headquarters_report(start_date: date | None = Query(default=None), end_date: date | None = Query(default=None), org_id: str = Depends(retail_tenant_id)):
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=89))
    if start > end:
        raise HTTPException(422, "start_date must be on or before end_date")
    with organization_connection(org_id) as conn:
        stores = conn.execute(
            "SELECT id,store_code,store_name,city,monthly_revenue_threshold FROM retail_stores WHERE organization_id=%s ORDER BY store_code",
            (org_id,),
        ).fetchall()
        reports = [_store_report(conn, org_id, store, start, end) for store in stores]
        ranked = sorted(reports, key=lambda r: r["data_analyst"]["gross_profit"], reverse=True)
        low_stock_stores = [r for r in reports if r["data_analyst"]["low_stock_skus"] > 0]
        expansion = []
        for store in stores:
            monthly = conn.execute(
                """SELECT date_trunc('month',sale_date)::date AS month, SUM(quantity*unit_price) AS revenue
                   FROM retail_sales WHERE organization_id=%s AND store_id=%s AND sale_date BETWEEN %s AND %s
                   GROUP BY 1 ORDER BY 1 DESC LIMIT 3""",
                (org_id, str(store["id"]), start, end),
            ).fetchall()
            threshold = Decimal(str(store["monthly_revenue_threshold"] or 0))
            consecutive = 0
            expected_month = end.replace(day=1)
            for month_row in monthly:
                month_value = month_row["month"]
                if month_value != expected_month or threshold <= 0 or Decimal(str(month_row["revenue"] or 0)) < threshold:
                    break
                consecutive += 1
                expected_month = (expected_month - timedelta(days=1)).replace(day=1)
            if threshold > 0 and consecutive >= 3:
                expansion.append({
                    "store_code": store["store_code"], "store_name": store["store_name"], "city": store["city"],
                    "monthly_revenue_threshold": float(threshold), "consecutive_months_above_threshold": consecutive,
                    "status": "expansion_candidate_for_review",
                    "reason": "The configured monthly revenue threshold was exceeded for three consecutive reported months. Validate catchment demand, rent, competition and cannibalisation before selecting a site.",
                })
    total_revenue = sum(r["data_analyst"]["revenue"] for r in reports)
    total_gross_profit = sum(r["data_analyst"]["gross_profit"] for r in reports)
    return {
        "agent": "ProfitPulse Headquarters Intelligence Agent",
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "store_count": len(reports),
        "company": {
            "total_revenue": round(total_revenue, 2), "total_gross_profit": round(total_gross_profit, 2),
            "gross_margin_pct": round((total_gross_profit / total_revenue * 100) if total_revenue else 0, 2),
            "stores_with_low_stock": len(low_stock_stores),
            "low_stock_sku_count": sum(r["data_analyst"]["low_stock_skus"] for r in reports),
        },
        "highest_gross_profit_store": ranked[0]["store"] if ranked else None,
        "store_ranking": [{
            **r["store"], "revenue": r["data_analyst"]["revenue"],
            "gross_profit": r["data_analyst"]["gross_profit"],
            "gross_margin_pct": r["data_analyst"]["gross_margin_pct"],
            "low_stock_skus": r["data_analyst"]["low_stock_skus"],
        } for r in ranked],
        "low_stock_stores": [{
            **r["store"], "low_stock_skus": r["data_analyst"]["low_stock_skus"],
            "tracked_skus": r["data_analyst"]["tracked_skus"],
        } for r in low_stock_stores],
        "expansion_candidates": expansion,
        "store_reports": reports,
        "important_note": "Reports use manually uploaded records. Expansion candidates are threshold-based leads for owner review, not definitive site-selection decisions.",
    }


@router.post("/headquarters/email")
def email_headquarters_report(payload: EmailRequest, start_date: date | None = Query(default=None), end_date: date | None = Query(default=None), org_id: str = Depends(retail_tenant_id)):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("REPORT_FROM_EMAIL") or smtp_user
    if not all([smtp_host, smtp_user, smtp_password, sender]):
        raise HTTPException(503, "Email is not configured. Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and REPORT_FROM_EMAIL.")
    report = headquarters_report(start_date, end_date, org_id)
    company = report["company"]
    lines = [
        "ProfitPulse AI | Multi-Store Retail Report",
        f"Reporting period: {report['period']['start_date']} to {report['period']['end_date']}",
        f"Stores reporting: {report['store_count']}",
        f"Total revenue: INR {company['total_revenue']:,.2f}",
        f"Total gross profit: INR {company['total_gross_profit']:,.2f}",
        f"Gross margin: {company['gross_margin_pct']:.2f}%",
        "", "Store ranking (by gross profit):",
    ]
    for index, store in enumerate(report["store_ranking"], start=1):
        lines.append(f"{index}. {store['name']} ({store['city']}): revenue INR {store['revenue']:,.2f}; gross profit INR {store['gross_profit']:,.2f}; low-stock SKUs {store['low_stock_skus']}")
    lines.extend(["", "Low-stock stores:"])
    lines.extend([f"- {s['name']} ({s['city']}): {s['low_stock_skus']} low-stock SKUs" for s in report["low_stock_stores"]] or ["- None detected"])
    lines.extend(["", "Expansion candidates for owner review:"])
    lines.extend([f"- {s['store_name']} ({s['city']}): exceeded INR {s['monthly_revenue_threshold']:,.0f}/month for three consecutive reported months" for s in report["expansion_candidates"]] or ["- No store met the configured three-month revenue threshold"])
    lines.extend(["", report["important_note"]])
    message = EmailMessage()
    message["Subject"] = f"ProfitPulse AI | Multi-store report | {report['period']['end_date']}"
    message["From"] = sender
    message["To"] = payload.recipient
    message.set_content("\n".join(lines))
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(message)
    except Exception as exc:
        raise HTTPException(502, f"Email delivery failed: {type(exc).__name__}") from exc
    return {"status": "sent", "recipient": payload.recipient, "subject": message["Subject"]}
