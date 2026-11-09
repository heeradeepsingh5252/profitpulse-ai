from datetime import date

from fastapi.testclient import TestClient

from profitpulse.main import app
from profitpulse.agent.two_agent import build_data_analyst_report


def test_data_analyst_report_uses_deterministic_inputs():
    report = build_data_analyst_report(
        period_start=date(2026, 8, 1),
        period_end=date(2026, 10, 31),
        currency="INR",
        metrics={
            "net_revenue": 100000,
            "gross_profit": 35000,
            "gross_margin_pct": 35,
            "operating_expenses": 42000,
            "operating_expense_ratio_pct": 42,
            "ebitda": -7000,
            "ebitda_margin_pct": -7,
            "pat": -9000,
        },
        monthly_trend=[
            {"month": "2026-09-01", "net_revenue": 50000, "operating_expenses": 18000},
            {"month": "2026-10-01", "net_revenue": 55000, "operating_expenses": 22000},
        ],
        products=[
            {"sku": "SKU-01", "product_name": "Gear Assembly", "units_sold": 25, "gross_profit": 12000},
            {"sku": "SKU-02", "product_name": "Valve Body", "units_sold": 10, "gross_profit": -500},
        ],
        inventory=[
            {"sku": "SKU-03", "product_name": "Bearing", "quantity_on_hand": 4, "reorder_alert": True, "snapshot_date": date(2026, 10, 31)},
        ],
    )

    assert report["agent"] == "AI Data Analyst"
    assert report["period"] == {"start_date": "2026-08-01", "end_date": "2026-10-31"}
    assert report["metrics"]["net_revenue"] == 100000
    assert any(item["id"] == "negative-product-margin" for item in report["findings"])
    assert any(item["id"] == "inventory-reorder" and item["severity"] == "watch" for item in report["findings"])
    assert any(item["id"] == "monthly-trend" and "+10.00%" in item["detail"] for item in report["findings"])


def test_two_agent_endpoint_requires_organization_header():
    with TestClient(app) as client:
        response = client.post("/api/v1/intelligence/analyse", json={"question": "Review manufacturing performance."})

    assert response.status_code == 422


def test_two_agent_endpoint_returns_combined_report(monkeypatch):
    def fake_analysis(*, question, organization_id, start_date, end_date, max_tool_rounds):
        assert question == "Review manufacturing performance."
        assert organization_id == "11111111-1111-4111-8111-111111111111"
        assert start_date == date(2026, 8, 1)
        assert end_date == date(2026, 10, 31)
        assert max_tool_rounds == 6
        return {
            "analysis_id": "demo-analysis",
            "period": {"start_date": "2026-08-01", "end_date": "2026-10-31"},
            "data_analyst": {"agent": "AI Data Analyst", "findings": []},
            "business_analyst": {"agent": "AI Business Analyst", "answer": "Prioritise supplier cost review."},
            "answer": "Prioritise supplier cost review.",
            "disclaimer": "Decision support only.",
        }

    monkeypatch.setattr("profitpulse.agent.two_agent.run_two_agent_analysis", fake_analysis)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/intelligence/analyse",
            headers={"X-Organization-ID": "11111111-1111-4111-8111-111111111111"},
            json={
                "question": "Review manufacturing performance.",
                "start_date": "2026-08-01",
                "end_date": "2026-10-31",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_id"] == "demo-analysis"
    assert payload["data_analyst"]["agent"] == "AI Data Analyst"
    assert payload["business_analyst"]["agent"] == "AI Business Analyst"


def test_two_agent_endpoint_rejects_invalid_period():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/intelligence/analyse",
            headers={"X-Organization-ID": "11111111-1111-4111-8111-111111111111"},
            json={
                "question": "Review manufacturing performance.",
                "start_date": "2026-10-31",
                "end_date": "2026-08-01",
            },
        )

    assert response.status_code == 422
