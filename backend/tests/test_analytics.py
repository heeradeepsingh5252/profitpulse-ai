from datetime import date

from profitpulse.analytics import (
    INVENTORY_HEALTH_SQL,
    PRODUCT_PERFORMANCE_SQL,
    REGIONAL_PERFORMANCE_SQL,
)


def test_product_performance_query_uses_delivered_orders_and_tenant_filter():
    assert "o.status='delivered'" in PRODUCT_PERFORMANCE_SQL
    assert "oi.organization_id=%s" in PRODUCT_PERFORMANCE_SQL
    assert "o.order_date BETWEEN %s AND %s" in PRODUCT_PERFORMANCE_SQL
    assert "oi.quantity * oi.unit_cost_snapshot" in PRODUCT_PERFORMANCE_SQL


def test_regional_performance_groups_unassigned_region_safely():
    assert "COALESCE(o.sales_region,'Unassigned')" in REGIONAL_PERFORMANCE_SQL
    assert "GROUP BY COALESCE(o.sales_region,'Unassigned')" in REGIONAL_PERFORMANCE_SQL


def test_inventory_health_uses_latest_snapshot_before_requested_date():
    assert "MAX(snapshot_date)" in INVENTORY_HEALTH_SQL
    assert "snapshot_date <= %s" in INVENTORY_HEALTH_SQL
    assert "quantity_on_hand <= reorder_level" in INVENTORY_HEALTH_SQL
