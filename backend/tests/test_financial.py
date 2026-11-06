from decimal import Decimal

from profitpulse.financial import (
    compute_balance_sheet,
    compute_financial_ratios,
    compute_financial_summary,
    fiscal_year_start,
)


def test_financial_summary_calculates_ebitda_and_pat():
    result = compute_financial_summary({
        "gross_sales": "1000000.00", "sales_returns": "20000.00", "cogs": "600000.00",
        "operating_expenses": "180000.00", "depreciation": "20000.00", "amortization": "5000.00",
        "interest_expense": "15000.00", "income_tax": "30000.00",
    })
    assert result["net_revenue"] == Decimal("980000.00")
    assert result["gross_profit"] == Decimal("380000.00")
    assert result["ebitda"] == Decimal("200000.00")
    assert result["ebit"] == Decimal("175000.00")
    assert result["pbt"] == Decimal("160000.00")
    assert result["pat"] == Decimal("130000.00")
    assert result["ebitda_margin_pct"] == Decimal("20.41")
    assert result["operating_expense_ratio_pct"] == Decimal("18.37")


def test_zero_revenue_returns_null_margins():
    result = compute_financial_summary({})
    assert result["ebitda"] == Decimal("0.00")
    assert result["gross_margin_pct"] is None
    assert result["ebitda_margin_pct"] is None


def test_returns_reduce_net_revenue():
    result = compute_financial_summary({"gross_sales": 500, "sales_returns": 50})
    assert result["net_revenue"] == Decimal("450.00")


def test_balance_sheet_reconciles_including_current_earnings():
    result = compute_balance_sheet({
        "cash": 1000, "receivable": 500, "inventory": 700,
        "fixed_asset": 800, "accumulated_depreciation": 100,
        "payable": 400, "debt": 300, "tax_payable": 50, "equity": 1800,
    }, current_earnings=350)
    assert result["total_assets"] == Decimal("2900.00")
    assert result["total_liabilities_and_equity"] == Decimal("2900.00")
    assert result["is_balanced"] is True


def test_balance_sheet_flags_unbalanced_ledger():
    result = compute_balance_sheet({"cash": 1000, "equity": 500}, current_earnings=0)
    assert result["balance_check_difference"] == Decimal("500.00")
    assert result["is_balanced"] is False


def test_fiscal_year_start_supports_april_to_march_india_year():
    from datetime import date
    assert fiscal_year_start(date(2026, 11, 5), 4) == date(2026, 4, 1)
    assert fiscal_year_start(date(2026, 2, 5), 4) == date(2025, 4, 1)


def test_financial_ratios_use_average_assets_and_equity():
    result = compute_financial_ratios(
        {"net_revenue": 1000, "gross_profit": 300, "ebitda": 180, "ebit": 150,
         "pat": 90, "interest_expense": 15, "operating_expenses": 120},
        {"total_assets": 800, "total_equity_including_current_earnings": 400, "debt": 200},
        {"total_assets": 1000, "total_equity_including_current_earnings": 500, "debt": 250},
    )
    assert result["gross_margin_pct"] == Decimal("30.00")
    assert result["return_on_assets_pct"] == Decimal("10.00")
    assert result["return_on_equity_pct"] == Decimal("20.00")
    assert result["asset_turnover_x"] == Decimal("1.11")
    assert result["debt_to_equity_x"] == Decimal("0.50")
    assert result["interest_coverage_x"] == Decimal("10.00")


def test_interest_coverage_is_null_when_no_interest_expense():
    result = compute_financial_ratios(
        {"net_revenue": 100, "gross_profit": 30, "ebitda": 20, "ebit": 18,
         "pat": 15, "interest_expense": 0, "operating_expenses": 10},
        {"total_assets": 100, "total_equity_including_current_earnings": 50, "debt": 0},
        {"total_assets": 100, "total_equity_including_current_earnings": 50, "debt": 0},
    )
    assert result["interest_coverage_x"] is None
