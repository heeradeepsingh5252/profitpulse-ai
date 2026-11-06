"""Tenant-scoped supply-chain query and calculation helpers for ProfitPulse."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def calculate_transit_days(actual_departure_at: datetime | None, actual_arrival_at: datetime | None) -> float | None:
    """Elapsed calendar days between carrier departure and arrival; incomplete timestamps return None."""
    if actual_departure_at is None or actual_arrival_at is None:
        return None
    seconds = (actual_arrival_at - actual_departure_at).total_seconds()
    if seconds < 0:
        raise ValueError("actual arrival cannot be before actual departure")
    return round(seconds / 86400, 2)


def calculate_delay_days(promised_at: datetime | None, actual_or_as_of: datetime | None) -> int | None:
    """Positive lateness in whole calendar days; early/on-time results are zero."""
    if promised_at is None or actual_or_as_of is None:
        return None
    return max(0, (actual_or_as_of.date() - promised_at.date()).days)


def calculate_otif(
    expected_date: date | None,
    received_date: date | None,
    quantity_ordered: Decimal | float,
    quantity_received: Decimal | float,
) -> bool | None:
    """On-time-in-full for a completed PO; incomplete PO data returns None."""
    if expected_date is None or received_date is None:
        return None
    return received_date <= expected_date and Decimal(str(quantity_received)) >= Decimal(str(quantity_ordered))


def load_supply_chain_overview(conn, organization_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
          (SELECT count(*) FROM purchase_orders po
            WHERE po.organization_id=%s AND po.status IN ('sent','partially_received')) AS open_purchase_orders,
          (SELECT count(*) FROM sc_inbound_shipments sh
            WHERE sh.organization_id=%s AND sh.status IN ('booked','picked_up','in_transit','at_origin_port','in_customs','at_destination_port','out_for_delivery','arrived_at_warehouse')) AS active_shipments,
          (SELECT count(*) FROM sc_inbound_shipments sh
            WHERE sh.organization_id=%s
              AND (sh.status IN ('delayed','exception') OR
                   (sh.current_eta_at < now() AND sh.status NOT IN ('delivered','cancelled','arrived_at_warehouse')))) AS delayed_shipments,
          (SELECT count(*) FROM sc_inbound_shipments sh
            WHERE sh.organization_id=%s
              AND sh.status IN ('booked','picked_up','in_transit','at_origin_port','in_customs','at_destination_port','out_for_delivery')
              AND COALESCE((SELECT max(ev.occurred_at) FROM sc_shipment_events ev
                            WHERE ev.organization_id=sh.organization_id AND ev.shipment_id=sh.id),sh.updated_at) < now() - interval '72 hours') AS stale_tracking_shipments,
          (SELECT avg(extract(epoch FROM (sh.actual_arrival_at-sh.actual_departure_at))/86400.0)
             FROM sc_inbound_shipments sh
            WHERE sh.organization_id=%s AND sh.actual_departure_at IS NOT NULL
              AND sh.actual_arrival_at IS NOT NULL AND sh.actual_arrival_at >= now() - interval '180 days') AS avg_transit_days,
          (SELECT COALESCE(sum(greatest(poi.quantity_ordered-poi.quantity_received,0)*poi.unit_cost),0)
             FROM purchase_orders po JOIN purchase_order_items poi
               ON poi.organization_id=po.organization_id AND poi.purchase_order_id=po.id
            WHERE po.organization_id=%s AND po.status IN ('sent','partially_received')) AS open_po_goods_value,
          (SELECT count(*) FROM sc_inbound_shipments sh WHERE sh.organization_id=%s) AS total_shipments
        """,
        (organization_id, organization_id, organization_id, organization_id,
         organization_id, organization_id, organization_id),
    ).fetchone()
    return _json_value(dict(row) if row else {})


def load_supplier_sites(conn, organization_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT s.id AS supplier_id,s.supplier_code,s.name AS supplier_name,
               s.email,s.phone,s.city AS supplier_city,s.state AS supplier_state,
               site.id AS supplier_site_id,site.site_code,site.site_name,site.site_type,
               site.origin_city,site.origin_state,site.origin_country,site.origin_country_code,
               site.origin_port,site.default_lead_time_days,site.preferred_transport_mode,
               site.is_primary,site.is_active
        FROM suppliers s
        LEFT JOIN sc_supplier_sites site
          ON site.organization_id=s.organization_id AND site.supplier_id=s.id AND site.is_active
        WHERE s.organization_id=%s
        ORDER BY s.name,site.is_primary DESC,site.site_name
        """,
        (organization_id,),
    ).fetchall()
    return [_json_value(dict(row)) for row in rows]


def load_purchase_orders(conn, organization_id: str, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT po.id,po.supplier_id,po.po_number,po.order_date,po.expected_date,po.received_date,po.status,
               po.total_amount,s.supplier_code,s.name AS supplier_name,
               count(DISTINCT poi.id) AS line_count,
               COALESCE(sum(poi.quantity_ordered),0) AS quantity_ordered,
               COALESCE(sum(poi.quantity_received),0) AS quantity_received,
               COALESCE(sum(greatest(poi.quantity_ordered-poi.quantity_received,0)*poi.unit_cost),0) AS outstanding_goods_value
        FROM purchase_orders po
        JOIN suppliers s ON s.organization_id=po.organization_id AND s.id=po.supplier_id
        LEFT JOIN purchase_order_items poi ON poi.organization_id=po.organization_id AND poi.purchase_order_id=po.id
        WHERE po.organization_id=%s AND (%s::text IS NULL OR po.status=%s)
        GROUP BY po.id,s.supplier_code,s.name
        ORDER BY po.order_date DESC,po.po_number DESC
        LIMIT %s
        """,
        (organization_id, status, status, limit),
    ).fetchall()
    return [_json_value(dict(row)) for row in rows]


def load_shipments(conn, organization_id: str, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT sh.id,sh.shipment_number,sh.status,sh.transport_mode,sh.incoterm,
               sh.carrier_name,sh.carrier_service,sh.tracking_number,
               sh.origin_city,sh.origin_state,sh.origin_country,sh.origin_port,sh.destination_port,
               sh.planned_departure_at,sh.actual_departure_at,sh.promised_arrival_at,
               sh.current_eta_at,sh.actual_arrival_at,sh.currency,sh.created_at,
               s.supplier_code,s.name AS supplier_name,w.name AS destination_warehouse,
               w.city AS destination_city,w.state AS destination_state,
               COALESCE(po_value.goods_value,0) AS goods_value,
               COALESCE(charge_value.charges_total,0) AS charges_total,
               last_event.event_code AS latest_event_code,last_event.location_name AS latest_location,
               last_event.occurred_at AS latest_event_at,
               CASE WHEN sh.actual_departure_at IS NOT NULL AND sh.actual_arrival_at IS NOT NULL
                    THEN round((extract(epoch FROM (sh.actual_arrival_at-sh.actual_departure_at))/86400.0)::numeric,2)
                    ELSE NULL END AS transit_days,
               CASE WHEN COALESCE(sh.promised_arrival_at,sh.current_eta_at) IS NULL THEN NULL
                    WHEN sh.actual_arrival_at IS NOT NULL
                    THEN greatest(0,(sh.actual_arrival_at::date-COALESCE(sh.promised_arrival_at,sh.current_eta_at)::date))
                    WHEN sh.status IN ('delayed','exception')
                    THEN greatest(0,(current_date-COALESCE(sh.promised_arrival_at,sh.current_eta_at)::date))
                    WHEN sh.current_eta_at < now()
                    THEN greatest(0,(current_date-sh.current_eta_at::date))
                    ELSE 0 END AS delay_days
        FROM sc_inbound_shipments sh
        JOIN suppliers s ON s.organization_id=sh.organization_id AND s.id=sh.supplier_id
        JOIN warehouses w ON w.organization_id=sh.organization_id AND w.id=sh.destination_warehouse_id
        LEFT JOIN LATERAL (
          SELECT sum(si.quantity_shipped*poi.unit_cost) AS goods_value
          FROM sc_shipment_items si
          JOIN purchase_order_items poi ON poi.organization_id=si.organization_id
               AND poi.purchase_order_id=si.purchase_order_id AND poi.id=si.purchase_order_item_id
          WHERE si.organization_id=sh.organization_id AND si.shipment_id=sh.id
        ) po_value ON true
        LEFT JOIN LATERAL (
          SELECT sum(c.amount) AS charges_total FROM sc_shipment_costs c
          WHERE c.organization_id=sh.organization_id AND c.shipment_id=sh.id AND c.currency=sh.currency
        ) charge_value ON true
        LEFT JOIN LATERAL (
          SELECT ev.event_code,ev.location_name,ev.occurred_at
          FROM sc_shipment_events ev WHERE ev.organization_id=sh.organization_id AND ev.shipment_id=sh.id
          ORDER BY ev.occurred_at DESC,ev.created_at DESC LIMIT 1
        ) last_event ON true
        WHERE sh.organization_id=%s AND (%s::text IS NULL OR sh.status=%s)
        ORDER BY CASE WHEN sh.status IN ('delayed','exception') THEN 0
                      WHEN sh.status NOT IN ('delivered','cancelled') THEN 1 ELSE 2 END,
                 sh.current_eta_at NULLS LAST,sh.created_at DESC
        LIMIT %s
        """,
        (organization_id, status, status, limit),
    ).fetchall()
    return [_json_value(dict(row)) for row in rows]


def load_shipment_timeline(conn, organization_id: str, shipment_id: str) -> dict[str, Any] | None:
    shipment = conn.execute(
        """SELECT sh.*,s.name AS supplier_name,s.supplier_code,w.name AS destination_warehouse,
                  w.city AS destination_city,w.state AS destination_state
             FROM sc_inbound_shipments sh
             JOIN suppliers s ON s.organization_id=sh.organization_id AND s.id=sh.supplier_id
             JOIN warehouses w ON w.organization_id=sh.organization_id AND w.id=sh.destination_warehouse_id
            WHERE sh.organization_id=%s AND sh.id=%s""",
        (organization_id, shipment_id),
    ).fetchone()
    if not shipment:
        return None
    events = conn.execute(
        """SELECT event_code,status_after,location_name,city,state,country,occurred_at,notes,source
             FROM sc_shipment_events WHERE organization_id=%s AND shipment_id=%s
            ORDER BY occurred_at,event_code""",
        (organization_id, shipment_id),
    ).fetchall()
    costs = conn.execute(
        """SELECT cost_type,description,amount,currency,charge_date,reference
             FROM sc_shipment_costs WHERE organization_id=%s AND shipment_id=%s
            ORDER BY charge_date,cost_type""",
        (organization_id, shipment_id),
    ).fetchall()
    items = conn.execute(
        """SELECT si.id AS shipment_item_id,si.purchase_order_id,po.po_number,
                  poi.product_id,p.sku,p.name AS product_name,
                  si.quantity_shipped,si.quantity_received,
                  greatest(si.quantity_shipped-si.quantity_received,0) AS quantity_outstanding,
                  poi.unit_cost
             FROM sc_shipment_items si
             JOIN purchase_orders po ON po.organization_id=si.organization_id AND po.id=si.purchase_order_id
             JOIN purchase_order_items poi ON poi.organization_id=si.organization_id
                  AND poi.purchase_order_id=si.purchase_order_id AND poi.id=si.purchase_order_item_id
             JOIN products p ON p.organization_id=poi.organization_id AND p.id=poi.product_id
            WHERE si.organization_id=%s AND si.shipment_id=%s
            ORDER BY p.name""",
        (organization_id, shipment_id),
    ).fetchall()
    return {
        "shipment": _json_value(dict(shipment)),
        "events": [_json_value(dict(row)) for row in events],
        "items": [_json_value(dict(row)) for row in items],
        "costs": [_json_value(dict(row)) for row in costs],
    }


def load_supplier_scorecards(conn, organization_id: str) -> list[dict[str, Any]]:
    """Calculate supplier procurement, fulfilment and delivery scorecards."""

    rows = conn.execute(
        """
        WITH po AS (
            SELECT
                po.supplier_id,

                COUNT(*) FILTER (
                    WHERE po.status <> 'cancelled'
                ) AS purchase_order_count,

                COUNT(*) FILTER (
                    WHERE po.status IN ('sent', 'partially_received')
                ) AS open_po_count,

                COUNT(*) FILTER (
                    WHERE po.status = 'received'
                      AND po.received_date IS NOT NULL
                ) AS completed_po_count,

                COUNT(*) FILTER (
                    WHERE po.status = 'received'
                      AND po.received_date IS NOT NULL
                      AND po.expected_date IS NOT NULL
                ) AS completed_po_with_due_date_count,

                COUNT(*) FILTER (
                    WHERE po.status = 'received'
                      AND po.received_date IS NOT NULL
                      AND po.expected_date IS NOT NULL
                      AND po.received_date <= po.expected_date
                ) AS on_time_po_count,

                AVG(po.received_date - po.order_date) FILTER (
                    WHERE po.status = 'received'
                      AND po.received_date IS NOT NULL
                ) AS avg_procurement_lead_days

            FROM purchase_orders po
            WHERE po.organization_id = %s
            GROUP BY po.supplier_id
        ),

        open_po AS (
            SELECT
                po.supplier_id,

                COALESCE(
                    SUM(
                        GREATEST(
                            poi.quantity_ordered - poi.quantity_received,
                            0
                        ) * poi.unit_cost
                    ),
                    0
                ) AS open_po_value

            FROM purchase_orders po
            JOIN purchase_order_items poi
                ON poi.organization_id = po.organization_id
               AND poi.purchase_order_id = po.id

            WHERE po.organization_id = %s
              AND po.status IN ('sent', 'partially_received')

            GROUP BY po.supplier_id
        ),

        item AS (
            SELECT
                po.supplier_id,

                COALESCE(SUM(poi.quantity_ordered), 0)
                    AS quantity_ordered,

                COALESCE(SUM(poi.quantity_received), 0)
                    AS quantity_received,

                COALESCE(
                    SUM(poi.quantity_ordered) FILTER (
                        WHERE po.status = 'received'
                          AND po.received_date IS NOT NULL
                    ),
                    0
                ) AS completed_quantity_ordered,

                COALESCE(
                    SUM(poi.quantity_received) FILTER (
                        WHERE po.status = 'received'
                          AND po.received_date IS NOT NULL
                    ),
                    0
                ) AS completed_quantity_received,

                COALESCE(
                    SUM(
                        GREATEST(
                            poi.quantity_ordered - poi.quantity_received,
                            0
                        )
                    ) FILTER (
                        WHERE po.status IN ('sent', 'partially_received')
                    ),
                    0
                ) AS outstanding_quantity

            FROM purchase_orders po
            JOIN purchase_order_items poi
                ON poi.organization_id = po.organization_id
               AND poi.purchase_order_id = po.id

            WHERE po.organization_id = %s
              AND po.status <> 'cancelled'

            GROUP BY po.supplier_id
        ),

        po_otif AS (
            SELECT
                po.id,
                po.supplier_id,
                po.expected_date,
                po.received_date,

                COUNT(poi.id) AS line_count,

                COUNT(poi.id) FILTER (
                    WHERE poi.quantity_received >= poi.quantity_ordered
                ) AS complete_line_count

            FROM purchase_orders po
            JOIN purchase_order_items poi
                ON poi.organization_id = po.organization_id
               AND poi.purchase_order_id = po.id

            WHERE po.organization_id = %s
              AND po.status = 'received'
              AND po.received_date IS NOT NULL
              AND po.expected_date IS NOT NULL

            GROUP BY
                po.id,
                po.supplier_id,
                po.expected_date,
                po.received_date
        ),

        otif AS (
            SELECT
                supplier_id,

                COUNT(*) AS completed_po_with_items,

                COUNT(*) FILTER (
                    WHERE received_date <= expected_date
                      AND complete_line_count = line_count
                ) AS otif_po_count

            FROM po_otif
            GROUP BY supplier_id
        ),

        ship AS (
            SELECT
                supplier_id,

                COUNT(*) AS shipment_count,

                COUNT(*) FILTER (
                    WHERE actual_departure_at IS NOT NULL
                      AND actual_arrival_at IS NOT NULL
                ) AS completed_shipments,

                COUNT(*) FILTER (
                    WHERE actual_departure_at IS NOT NULL
                      AND actual_arrival_at IS NOT NULL
                      AND promised_arrival_at IS NOT NULL
                ) AS completed_shipments_with_due_date,

                AVG(
                    EXTRACT(
                        EPOCH FROM (
                            actual_arrival_at - actual_departure_at
                        )
                    ) / 86400.0
                ) FILTER (
                    WHERE actual_departure_at IS NOT NULL
                      AND actual_arrival_at IS NOT NULL
                ) AS avg_transit_days,

                COUNT(*) FILTER (
                    WHERE actual_arrival_at IS NOT NULL
                      AND promised_arrival_at IS NOT NULL
                      AND actual_arrival_at <= promised_arrival_at
                ) AS on_time_shipments

            FROM sc_inbound_shipments

            WHERE organization_id = %s
              AND status <> 'cancelled'

            GROUP BY supplier_id
        ),

        receipt AS (
            SELECT
                sh.supplier_id,

                COALESCE(SUM(ri.quantity_rejected), 0)
                    AS rejected_qty,

                COALESCE(SUM(ri.quantity_received), 0)
                    AS received_qty

            FROM sc_goods_receipts gr

            JOIN sc_goods_receipt_items ri
                ON ri.organization_id = gr.organization_id
               AND ri.goods_receipt_id = gr.id

            JOIN sc_inbound_shipments sh
                ON sh.organization_id = gr.organization_id
               AND sh.id = gr.shipment_id

            WHERE gr.organization_id = %s

            GROUP BY sh.supplier_id
        )

        SELECT
            s.id AS supplier_id,
            s.supplier_code,
            s.name AS supplier_name,

            COALESCE(po.purchase_order_count, 0)
                AS purchase_order_count,

            COALESCE(po.open_po_count, 0)
                AS open_po_count,

            COALESCE(po.completed_po_count, 0)
                AS completed_po_count,

            COALESCE(po.completed_po_with_due_date_count, 0)
                AS completed_po_with_due_date_count,

            COALESCE(po.on_time_po_count, 0)
                AS on_time_po_count,

            CASE
                WHEN COALESCE(
                    po.completed_po_with_due_date_count, 0
                ) > 0
                THEN ROUND(
                    (
                        po.on_time_po_count::numeric
                        / po.completed_po_with_due_date_count
                    ) * 100,
                    2
                )
                ELSE NULL
            END AS on_time_po_pct,

            CASE
                WHEN COALESCE(otif.completed_po_with_items, 0) > 0
                THEN ROUND(
                    (
                        otif.otif_po_count::numeric
                        / otif.completed_po_with_items
                    ) * 100,
                    2
                )
                ELSE NULL
            END AS otif_pct,

            COALESCE(otif.otif_po_count, 0)
                AS otif_po_count,

            ROUND(po.avg_procurement_lead_days::numeric, 2)
                AS avg_procurement_lead_days,

            COALESCE(item.quantity_ordered, 0)
                AS quantity_ordered,

            COALESCE(item.quantity_received, 0)
                AS quantity_received,

            CASE
                WHEN COALESCE(item.quantity_ordered, 0) > 0
                THEN ROUND(
                    (
                        item.quantity_received::numeric
                        / item.quantity_ordered
                    ) * 100,
                    2
                )
                ELSE NULL
            END AS fill_rate_pct,

            COALESCE(item.completed_quantity_ordered, 0)
                AS completed_quantity_ordered,

            COALESCE(item.completed_quantity_received, 0)
                AS completed_quantity_received,

            CASE
                WHEN COALESCE(item.completed_quantity_ordered, 0) > 0
                THEN ROUND(
                    (
                        item.completed_quantity_received::numeric
                        / item.completed_quantity_ordered
                    ) * 100,
                    2
                )
                ELSE NULL
            END AS completed_po_fill_rate_pct,

            COALESCE(item.outstanding_quantity, 0)
                AS outstanding_quantity,

            COALESCE(ship.shipment_count, 0)
                AS shipment_count,

            COALESCE(ship.completed_shipments, 0)
                AS completed_shipments,

            COALESCE(ship.completed_shipments_with_due_date, 0)
                AS completed_shipments_with_due_date,

            COALESCE(ship.on_time_shipments, 0)
                AS on_time_shipments,

            CASE
                WHEN COALESCE(
                    ship.completed_shipments_with_due_date, 0
                ) > 0
                THEN ROUND(
                    (
                        ship.on_time_shipments::numeric
                        / ship.completed_shipments_with_due_date
                    ) * 100,
                    2
                )
                ELSE NULL
            END AS on_time_shipment_pct,

            ROUND(ship.avg_transit_days::numeric, 2)
                AS avg_transit_days,

            COALESCE(receipt.rejected_qty, 0)
                AS rejected_quantity,

            COALESCE(receipt.received_qty, 0)
                AS receipt_quantity,

            CASE
                WHEN COALESCE(receipt.received_qty, 0) > 0
                THEN ROUND(
                    (
                        receipt.rejected_qty::numeric
                        / receipt.received_qty
                    ) * 100,
                    2
                )
                ELSE NULL
            END AS rejected_quantity_pct,

            COALESCE(open_po.open_po_value, 0)
                AS open_po_value

        FROM suppliers s

        LEFT JOIN po
            ON po.supplier_id = s.id

        LEFT JOIN open_po
            ON open_po.supplier_id = s.id

        LEFT JOIN item
            ON item.supplier_id = s.id

        LEFT JOIN otif
            ON otif.supplier_id = s.id

        LEFT JOIN ship
            ON ship.supplier_id = s.id

        LEFT JOIN receipt
            ON receipt.supplier_id = s.id

        WHERE s.organization_id = %s

        ORDER BY
            on_time_po_pct NULLS LAST,
            avg_procurement_lead_days,
            s.name
        """,
        (
            organization_id,
            organization_id,
            organization_id,
            organization_id,
            organization_id,
            organization_id,
            organization_id,
        ),
    ).fetchall()

    return [_json_value(dict(row)) for row in rows]


def load_supply_chain_exceptions(conn, organization_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT sh.id,sh.shipment_number,sh.status,sh.current_eta_at,sh.promised_arrival_at,
               sh.carrier_name,sh.tracking_number,s.name AS supplier_name,
               sh.origin_city,sh.origin_country,w.city AS destination_city,
               last_event.occurred_at AS latest_event_at,last_event.location_name AS latest_location,
               CASE WHEN sh.status IN ('delayed','exception') THEN sh.status
                    WHEN sh.current_eta_at < now() THEN 'eta_overdue'
                    ELSE 'tracking_stale' END AS exception_type,
               CASE WHEN sh.current_eta_at < now() THEN greatest(0,current_date-sh.current_eta_at::date)
                    ELSE NULL END AS overdue_days
        FROM sc_inbound_shipments sh
        JOIN suppliers s ON s.organization_id=sh.organization_id AND s.id=sh.supplier_id
        JOIN warehouses w ON w.organization_id=sh.organization_id AND w.id=sh.destination_warehouse_id
        LEFT JOIN LATERAL (
          SELECT occurred_at,location_name FROM sc_shipment_events ev
          WHERE ev.organization_id=sh.organization_id AND ev.shipment_id=sh.id
          ORDER BY occurred_at DESC,created_at DESC LIMIT 1
        ) last_event ON true
        WHERE sh.organization_id=%s AND sh.status NOT IN ('delivered','cancelled','arrived_at_warehouse')
          AND (sh.status IN ('delayed','exception') OR sh.current_eta_at < now()
               OR COALESCE(last_event.occurred_at,sh.updated_at) < now()-interval '72 hours')
        ORDER BY sh.current_eta_at NULLS FIRST,sh.updated_at
        LIMIT 100
        """,
        (organization_id,),
    ).fetchall()
    return [_json_value(dict(row)) for row in rows]
