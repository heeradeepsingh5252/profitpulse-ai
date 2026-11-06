import pytest

from profitpulse.agent.prompts import build_system_prompt
from profitpulse.agent.tools import (
    _add_month_over_month_changes,
    _group_monthly_expense_rows,
    _validate_period,
    build_business_tools,
)


def test_business_tools_are_bound_without_tenant_argument():
    tools = build_business_tools("11111111-1111-4111-8111-111111111111")
    names = {tool.name for tool in tools}

    assert names == {
        "get_data_coverage",
        "get_financial_summary",
        "get_balance_sheet",
        "get_financial_ratios",
        "get_expense_breakdown",
        "get_monthly_expense_breakdown",
        "get_product_performance",
        "get_regional_performance",
        "get_inventory_health",
        "get_monthly_financial_trend",
        "get_budget_variance",
    }
    assert all("organization_id" not in tool.args for tool in tools)


def test_period_validation_accepts_valid_range():
    start, end = _validate_period("2026-08-01", "2026-10-31")
    assert str(start) == "2026-08-01"
    assert str(end) == "2026-10-31"


@pytest.mark.parametrize(
    "start,end,message",
    [
        ("not-a-date", "2026-10-31", "YYYY-MM-DD"),
        ("2026-10-31", "2026-08-01", "on or after"),
        ("2020-01-01", "2026-10-31", "three-year"),
    ],
)
def test_period_validation_rejects_invalid_ranges(start, end, message):
    with pytest.raises(ValueError, match=message):
        _validate_period(start, end)


def test_prompt_requires_evidence_and_prohibits_invented_numbers():
    prompt = build_system_prompt()
    assert "Never invent, estimate, or infer a financial amount" in prompt
    assert "Never write SQL yourself" in prompt
    assert "Distinguish facts, calculations, hypotheses, and recommendations" in prompt
    assert "get_monthly_expense_breakdown" in prompt
    assert "Use precomputed ratio fields" in prompt
    assert "[Evidence: tool_name, period/date]" in prompt
    assert "The available data is insufficient to identify the cause." in prompt


def test_monthly_expense_grouping_calculates_account_shares_per_month():
    rows = [
        {"month_start": "2026-08-01", "account_code": "6100", "account_name": "Rent", "amount": 100},
        {"month_start": "2026-08-01", "account_code": "6200", "account_name": "Marketing", "amount": 100},
        {"month_start": "2026-09-01", "account_code": "6100", "account_name": "Rent", "amount": 300},
    ]

    result = _group_monthly_expense_rows(rows)

    assert len(result) == 2
    assert result[0]["month"] == "2026-08-01"
    assert result[0]["total_operating_expenses"] == 200.0
    assert [item["share_of_monthly_operating_expenses_pct"] for item in result[0]["accounts"]] == [50.0, 50.0]
    assert result[1]["total_operating_expenses"] == 300.0
    assert result[1]["accounts"][0]["share_of_monthly_operating_expenses_pct"] == 100.0
    assert result[0]["evidence_id"] == "ledger.operating_expenses.2026-08-01"


def test_monthly_expense_grouping_empty_input_returns_no_claimable_months():
    assert _group_monthly_expense_rows([]) == []


def test_month_over_month_changes_are_computed_deterministically():
    months = [
        {"month": "2026-08-01", "net_revenue": 371292.79, "operating_expenses": 190000.0},
        {"month": "2026-09-01", "net_revenue": 298322.56, "operating_expenses": 202000.0},
        {"month": "2026-10-01", "net_revenue": 237132.09, "operating_expenses": 276000.0},
    ]
    result = _add_month_over_month_changes(months)
    assert result[0]["month_over_month"]["comparison_status"] == "no_prior_month_in_result"
    assert result[1]["month_over_month"]["net_revenue_change_amount"] == -72970.23
    assert result[1]["month_over_month"]["net_revenue_change_pct"] == -19.65
    assert result[2]["month_over_month"]["net_revenue_change_pct"] == -20.51
    assert result[2]["month_over_month"]["operating_expenses_change_amount"] == 74000.0
    assert result[2]["month_over_month"]["operating_expenses_change_pct"] == 36.63


def test_month_over_month_zero_prior_value_has_no_percentage():
    result = _add_month_over_month_changes([
        {"month": "2026-08-01", "net_revenue": 0, "operating_expenses": 0},
        {"month": "2026-09-01", "net_revenue": 100, "operating_expenses": 50},
    ])
    assert result[1]["month_over_month"]["net_revenue_change_pct"] is None
    assert result[1]["month_over_month"]["operating_expenses_change_pct"] is None


def test_month_over_month_skips_comparison_when_calendar_month_is_missing():
    result = _add_month_over_month_changes([
        {"month": "2026-08-01", "net_revenue": 100, "operating_expenses": 20},
        {"month": "2026-10-01", "net_revenue": 80, "operating_expenses": 25},
    ])
    comparison = result[1]["month_over_month"]
    assert comparison["comparison_status"] == "previous_calendar_month_missing_from_results"
    assert "net_revenue_change_pct" not in comparison
