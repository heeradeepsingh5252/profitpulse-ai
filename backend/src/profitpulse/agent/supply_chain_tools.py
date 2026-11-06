"""Read-only, tenant-bound supply-chain tools for the ProfitPulse agent."""
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from profitpulse.db import organization_connection
from profitpulse.supply_chain import (
    load_shipments,
    load_supplier_scorecards,
    load_supply_chain_exceptions,
    load_supply_chain_overview,
    load_shipment_timeline,
)


class ShipmentListArgs(BaseModel):
    status: str | None = Field(default=None, description="Optional shipment status filter.")
    limit: int = Field(default=20, ge=1, le=100)


class ShipmentTimelineArgs(BaseModel):
    shipment_id: str = Field(min_length=36, max_length=36, description="Shipment UUID returned by get_inbound_shipments.")


def build_supply_chain_tools(organization_id: str) -> list[StructuredTool]:
    """Build supply-chain analytics tools fixed to the API request's organization."""

    def get_supply_chain_overview() -> dict:
        """Summarize open POs, active inbound shipments, delays, stale tracking and average transit time."""
        with organization_connection(organization_id) as conn:
            return load_supply_chain_overview(conn, organization_id)

    def get_inbound_shipments(status: str | None = None, limit: int = 20) -> dict:
        """List inbound shipment origins, destination, carrier, tracking number, ETA, costs and latest tracking event."""
        if not 1 <= limit <= 100:
            return {"error": "limit must be between 1 and 100"}
        allowed = {"planned","booked","picked_up","in_transit","at_origin_port","in_customs",
                   "at_destination_port","out_for_delivery","arrived_at_warehouse","delayed","exception","delivered","cancelled"}
        if status is not None and status not in allowed:
            return {"error": "Unsupported shipment status filter"}
        with organization_connection(organization_id) as conn:
            rows = load_shipments(conn, organization_id, status, limit)
        return {
            "shipments": rows,
            "count": len(rows),
            "tracking_note": "Shipment tracking events are manually entered in this development release; live carrier connections are not configured.",
        }

    def get_shipment_timeline(shipment_id: str) -> dict:
        """Retrieve the recorded milestone history, shipment items and freight/handling charges for one tenant shipment."""
        with organization_connection(organization_id) as conn:
            result = load_shipment_timeline(conn, organization_id, shipment_id)
        return result or {"error": "Shipment not found for this organization"}

    def get_supplier_scorecards() -> dict:
        """Compare supplier on-time delivery, PO fill rate, procurement lead time, transit time and rejected quantity."""
        with organization_connection(organization_id) as conn:
            rows = load_supplier_scorecards(conn, organization_id)
        return {"suppliers": rows, "definitions": {
            "on_time_po_pct": "Completed purchase orders received on or before expected date.",
            "fill_rate_pct": "Accepted quantity recorded on purchase-order lines divided by quantity ordered; rejected units are excluded.",
            "avg_procurement_lead_days": "Calendar days between purchase order date and recorded receipt date.",
            "avg_transit_days": "Calendar days between actual departure and actual arrival.",
            "rejected_quantity_pct": "Rejected quantity divided by physically received quantity.",
        }}

    def get_supply_chain_exceptions() -> dict:
        """Identify delayed/exception shipments, past-due ETAs and tracking with no update for more than 72 hours."""
        with organization_connection(organization_id) as conn:
            rows = load_supply_chain_exceptions(conn, organization_id)
        return {"exceptions": rows, "count": len(rows)}

    return [
        StructuredTool.from_function(
            get_supply_chain_overview,
            name="get_supply_chain_overview",
            description="Retrieve supply-chain KPIs including open purchase orders, active shipments, overdue shipments, stale tracking, open PO goods value and historical average transit days.",
        ),
        StructuredTool.from_function(
            get_inbound_shipments,
            name="get_inbound_shipments",
            description="Inspect inbound shipment origins, destinations, carriers, tracking numbers, ETAs, current status, latest event, shipment goods value and recorded charges. Use this to answer where goods are coming from and when they may arrive.",
            args_schema=ShipmentListArgs,
        ),
        StructuredTool.from_function(
            get_shipment_timeline,
            name="get_shipment_timeline",
            description="Retrieve a shipment's event timeline, associated products and quantities, and recorded shipment charges. Use when a user asks why or when a particular shipment moved.",
            args_schema=ShipmentTimelineArgs,
        ),
        StructuredTool.from_function(
            get_supplier_scorecards,
            name="get_supplier_scorecards",
            description="Compare supplier purchase-order on-time rate, fill rate, procurement lead time, shipment transit time and rejected quantity. State when a metric is unavailable due to insufficient completed records.",
        ),
        StructuredTool.from_function(
            get_supply_chain_exceptions,
            name="get_supply_chain_exceptions",
            description="Find delayed and exceptional shipments, overdue ETAs and tracking records with no update for more than 72 hours. Treat these as investigation alerts, not proof of supplier fault.",
        ),
    ]
