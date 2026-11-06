from datetime import date
from decimal import Decimal


def _float(value):
    return float(value) if value is not None else None


PRODUCT_PERFORMANCE_SQL = """
SELECT p.sku, p.name AS product_name, p.category,
       COALESCE(SUM(oi.quantity),0) AS units_sold,
       COALESCE(SUM(oi.line_total),0) AS net_sales,
       COALESCE(SUM(oi.quantity * oi.unit_cost_snapshot),0) AS cogs,
       COALESCE(SUM(oi.line_total - oi.quantity * oi.unit_cost_snapshot),0) AS gross_profit,
       COUNT(DISTINCT o.id) AS order_count
FROM order_items oi
JOIN orders o ON o.organization_id=oi.organization_id AND o.id=oi.order_id
JOIN products p ON p.organization_id=oi.organization_id AND p.id=oi.product_id
WHERE oi.organization_id=%s
  AND o.status='delivered'
  AND o.order_date BETWEEN %s AND %s
GROUP BY p.sku,p.name,p.category
ORDER BY gross_profit DESC, net_sales DESC
LIMIT %s
"""

REGIONAL_PERFORMANCE_SQL = """
SELECT COALESCE(o.sales_region,'Unassigned') AS region,
       COUNT(DISTINCT o.id) AS order_count,
       COALESCE(SUM(oi.line_total),0) AS net_sales,
       COALESCE(SUM(oi.quantity * oi.unit_cost_snapshot),0) AS cogs,
       COALESCE(SUM(oi.line_total - oi.quantity * oi.unit_cost_snapshot),0) AS gross_profit
FROM orders o
JOIN order_items oi ON oi.organization_id=o.organization_id AND oi.order_id=o.id
WHERE o.organization_id=%s AND o.status='delivered'
  AND o.order_date BETWEEN %s AND %s
GROUP BY COALESCE(o.sales_region,'Unassigned')
ORDER BY gross_profit DESC
"""

INVENTORY_HEALTH_SQL = """
WITH latest_snapshot AS (
  SELECT product_id, warehouse_id, MAX(snapshot_date) AS snapshot_date
  FROM inventory_snapshots
  WHERE organization_id=%s AND snapshot_date <= %s
  GROUP BY product_id, warehouse_id
), post_snapshot_movements AS (
  SELECT im.product_id,im.warehouse_id,
         COALESCE(SUM(im.quantity_delta),0) AS quantity_delta,
         COALESCE(SUM(im.quantity_delta*im.unit_cost),0) AS inventory_value_delta
  FROM inventory_movements im
  JOIN latest_snapshot ls ON ls.product_id=im.product_id AND ls.warehouse_id=im.warehouse_id
  WHERE im.organization_id=%s AND im.movement_date > ls.snapshot_date AND im.movement_date <= %s
  GROUP BY im.product_id,im.warehouse_id
), stock AS (
  SELECT p.id, p.sku, p.name AS product_name, p.category, p.reorder_level,
         SUM(s.quantity_on_hand + COALESCE(m.quantity_delta,0)) AS quantity_on_hand,
         SUM(s.quantity_on_hand*s.unit_cost + COALESCE(m.inventory_value_delta,0)) AS inventory_value,
         MAX(s.snapshot_date) AS snapshot_date
  FROM latest_snapshot ls
  JOIN inventory_snapshots s
    ON s.organization_id=%s AND s.product_id=ls.product_id
   AND s.warehouse_id=ls.warehouse_id AND s.snapshot_date=ls.snapshot_date
  LEFT JOIN post_snapshot_movements m ON m.product_id=ls.product_id AND m.warehouse_id=ls.warehouse_id
  JOIN products p ON p.organization_id=s.organization_id AND p.id=s.product_id
  GROUP BY p.id,p.sku,p.name,p.category,p.reorder_level
)
SELECT *, (quantity_on_hand <= reorder_level) AS reorder_alert
FROM stock
ORDER BY reorder_alert DESC, quantity_on_hand ASC, product_name
"""



def load_product_performance(conn, organization_id: str, start_date: date, end_date: date, limit: int = 20):
    rows = conn.execute(
        PRODUCT_PERFORMANCE_SQL, (organization_id, start_date, end_date, limit)
    ).fetchall()
    return [{key: (_float(value) if key not in {"sku", "product_name", "category", "order_count"} else value)
             for key, value in dict(row).items()} for row in rows]


def load_regional_performance(conn, organization_id: str, start_date: date, end_date: date):
    rows = conn.execute(REGIONAL_PERFORMANCE_SQL, (organization_id, start_date, end_date)).fetchall()
    return [{key: (_float(value) if key in {"net_sales", "cogs", "gross_profit"} else value)
             for key, value in dict(row).items()} for row in rows]


def load_inventory_health(conn, organization_id: str, as_of_date: date):
    rows = conn.execute(INVENTORY_HEALTH_SQL, (organization_id, as_of_date, organization_id, as_of_date, organization_id)).fetchall()
    return [{key: (_float(value) if key in {"quantity_on_hand", "inventory_value"} else value)
             for key, value in dict(row).items()} for row in rows]
