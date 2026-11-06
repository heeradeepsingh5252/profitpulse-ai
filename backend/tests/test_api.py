from fastapi.testclient import TestClient
from profitpulse.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_day2_financial_and_analytics_routes_are_registered():
    paths = {route.path for route in app.routes}
    expected = {
        "/api/v1/financial/balance-sheet",
        "/api/v1/financial/ratios",
        "/api/v1/financial/monthly-trend",
        "/api/v1/financial/budget-variance",
        "/api/v1/analytics/product-performance",
        "/api/v1/analytics/regional-performance",
        "/api/v1/analytics/inventory-health",
    }
    assert expected.issubset(paths)


def test_financial_period_validation_returns_422_without_database_call():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/financial/ratios?start_date=2026-10-31&end_date=2026-08-01",
            headers={"X-Organization-ID": "11111111-1111-4111-8111-111111111111"},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "end_date must be on or after start_date"
