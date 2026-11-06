from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def money(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def percentage(numerator: Any, denominator: Any) -> Decimal | None:
    numerator_d = money(numerator)
    denominator_d = money(denominator)
    if denominator_d == 0:
        return None
    return (numerator_d / denominator_d * Decimal("100")).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def compute_financial_summary(totals: dict[str, Any]) -> dict[str, Decimal | None]:
    """Compute management P&L metrics from positive signed ledger magnitudes.

    Assumptions for this starter:
    - Gross sales and sales returns are classified in the chart of accounts.
    - Operating expenses exclude depreciation, amortisation, interest and income tax.
    - Non-operating income is not yet modelled as a separate category.
    """
    gross_sales = money(totals.get("gross_sales"))
    sales_returns = money(totals.get("sales_returns"))
    cogs = money(totals.get("cogs"))
    operating_expenses = money(totals.get("operating_expenses"))
    depreciation = money(totals.get("depreciation"))
    amortization = money(totals.get("amortization"))
    interest = money(totals.get("interest_expense"))
    tax = money(totals.get("income_tax"))

    net_revenue = money(gross_sales - sales_returns)
    gross_profit = money(net_revenue - cogs)
    ebitda = money(gross_profit - operating_expenses)
    total_da = money(depreciation + amortization)
    ebit = money(ebitda - total_da)
    pbt = money(ebit - interest)
    pat = money(pbt - tax)

    return {
        "gross_sales": gross_sales,
        "sales_returns": sales_returns,
        "net_revenue": net_revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "gross_margin_pct": percentage(gross_profit, net_revenue),
        "operating_expenses": operating_expenses,
        "ebitda": ebitda,
        "ebitda_margin_pct": percentage(ebitda, net_revenue),
        "depreciation": depreciation,
        "amortization": amortization,
        "total_depreciation_amortization": total_da,
        "ebit": ebit,
        "interest_expense": interest,
        "pbt": pbt,
        "income_tax": tax,
        "pat": pat,
        "pat_margin_pct": percentage(pat, net_revenue),
        "operating_expense_ratio_pct": percentage(operating_expenses, net_revenue),
    }


FINANCIAL_TOTALS_SQL = """
SELECT
  COALESCE(SUM(CASE WHEN a.financial_category = 'revenue' THEN jl.credit - jl.debit ELSE 0 END), 0) AS gross_sales,
  COALESCE(SUM(CASE WHEN a.financial_category = 'contra_revenue' THEN jl.debit - jl.credit ELSE 0 END), 0) AS sales_returns,
  COALESCE(SUM(CASE WHEN a.financial_category = 'cogs' THEN jl.debit - jl.credit ELSE 0 END), 0) AS cogs,
  COALESCE(SUM(CASE WHEN a.financial_category = 'operating_expense' THEN jl.debit - jl.credit ELSE 0 END), 0) AS operating_expenses,
  COALESCE(SUM(CASE WHEN a.financial_category = 'depreciation' THEN jl.debit - jl.credit ELSE 0 END), 0) AS depreciation,
  COALESCE(SUM(CASE WHEN a.financial_category = 'amortization' THEN jl.debit - jl.credit ELSE 0 END), 0) AS amortization,
  COALESCE(SUM(CASE WHEN a.financial_category = 'interest_expense' THEN jl.debit - jl.credit ELSE 0 END), 0) AS interest_expense,
  COALESCE(SUM(CASE WHEN a.financial_category = 'income_tax' THEN jl.debit - jl.credit ELSE 0 END), 0) AS income_tax
FROM journal_entries je
JOIN journal_lines jl ON jl.organization_id = je.organization_id AND jl.journal_entry_id = je.id
JOIN gl_accounts a ON a.organization_id = jl.organization_id AND a.id = jl.account_id
WHERE je.organization_id = %s AND je.status = 'posted'
  AND je.entry_date BETWEEN %s AND %s
"""

BALANCE_SHEET_TOTALS_SQL = """
SELECT
  a.financial_category,
  COALESCE(SUM(
    CASE WHEN a.normal_balance = 'debit' THEN jl.debit - jl.credit
         ELSE jl.credit - jl.debit END
  ), 0) AS balance
FROM journal_entries je
JOIN journal_lines jl
  ON jl.organization_id = je.organization_id
 AND jl.journal_entry_id = je.id
JOIN gl_accounts a
  ON a.organization_id = jl.organization_id
 AND a.id = jl.account_id
WHERE je.organization_id = %s
  AND je.status = 'posted'
  AND je.entry_date <= %s
  AND a.financial_statement = 'balance_sheet'
GROUP BY a.financial_category
"""


def _as_float_dict(values: dict[str, Any]) -> dict[str, Any]:
    """Convert Decimal values for JSON while preserving booleans and strings."""
    return {
        key: (float(value) if isinstance(value, Decimal) else value)
        for key, value in values.items()
    }


def load_financial_summary(conn, organization_id: str, start_date, end_date) -> dict:
    row = conn.execute(
        FINANCIAL_TOTALS_SQL, (organization_id, start_date, end_date)
    ).fetchone()
    return _as_float_dict(compute_financial_summary(row or {}))


def fiscal_year_start(as_of_date: date, start_month: int) -> date:
    """Return the first day of the fiscal year containing as_of_date."""
    year = as_of_date.year if as_of_date.month >= start_month else as_of_date.year - 1
    return date(year, start_month, 1)


def compute_balance_sheet(category_totals: dict[str, Any], current_earnings: Any) -> dict[str, Any]:
    """Compute a classified balance sheet from normal-balance ledger amounts.

    Debt maturity is not split into current/non-current portions in Day 1, so this
    response does not present a conventional current ratio or quick ratio.
    """
    categories = {
        key: money(category_totals.get(key))
        for key in (
            "cash", "receivable", "inventory", "other_asset", "fixed_asset",
            "accumulated_depreciation", "payable", "debt", "tax_payable", "equity",
        )
    }
    cash = categories["cash"]
    receivables = categories["receivable"]
    inventory = categories["inventory"]
    other_assets = categories["other_asset"]
    gross_fixed_assets = categories["fixed_asset"]
    accumulated_depreciation = categories["accumulated_depreciation"]
    accounts_payable = categories["payable"]
    debt = categories["debt"]
    tax_payable = categories["tax_payable"]
    contributed_equity = categories["equity"]
    current_earnings_d = money(current_earnings)

    current_assets = money(cash + receivables + inventory)
    net_fixed_assets = money(gross_fixed_assets - accumulated_depreciation)
    total_assets = money(current_assets + other_assets + net_fixed_assets)
    total_liabilities = money(accounts_payable + debt + tax_payable)
    total_equity = money(contributed_equity + current_earnings_d)
    total_liabilities_equity = money(total_liabilities + total_equity)
    difference = money(total_assets - total_liabilities_equity)

    return {
        "cash_and_cash_equivalents": cash,
        "accounts_receivable": receivables,
        "inventory": inventory,
        "total_current_assets": current_assets,
        "other_assets": other_assets,
        "gross_fixed_assets": gross_fixed_assets,
        "accumulated_depreciation": accumulated_depreciation,
        "net_fixed_assets": net_fixed_assets,
        "total_assets": total_assets,
        "accounts_payable": accounts_payable,
        "debt": debt,
        "tax_payable": tax_payable,
        "total_liabilities": total_liabilities,
        "contributed_equity": contributed_equity,
        "current_fiscal_year_earnings": current_earnings_d,
        "total_equity_including_current_earnings": total_equity,
        "total_liabilities_and_equity": total_liabilities_equity,
        "balance_check_difference": difference,
        "is_balanced": abs(difference) <= Decimal("0.05"),
        "operating_working_capital_proxy_excluding_cash_and_borrowings": money(
            receivables + inventory - accounts_payable - tax_payable
        ),
    }


def load_balance_sheet(conn, organization_id: str, as_of_date: date) -> dict:
    rows = conn.execute(
        BALANCE_SHEET_TOTALS_SQL, (organization_id, as_of_date)
    ).fetchall()
    category_totals = {row["financial_category"]: row["balance"] for row in rows}

    org = conn.execute(
        "SELECT fiscal_year_start_month FROM organizations WHERE id = %s",
        (organization_id,),
    ).fetchone()
    fy_start_month = int(org["fiscal_year_start_month"]) if org else 4
    fy_start = fiscal_year_start(as_of_date, fy_start_month)
    ytd_totals = conn.execute(
        FINANCIAL_TOTALS_SQL, (organization_id, fy_start, as_of_date)
    ).fetchone()
    ytd_pnl = compute_financial_summary(ytd_totals or {})
    result = compute_balance_sheet(category_totals, ytd_pnl["pat"])
    return _as_float_dict(result) | {"as_of_date": str(as_of_date), "fiscal_year_start": str(fy_start)}


def compute_financial_ratios(
    period_metrics: dict[str, Any],
    opening_balance_sheet: dict[str, Any],
    closing_balance_sheet: dict[str, Any],
) -> dict[str, Any]:
    """Compute selected ratios using average balances where appropriate."""
    opening_assets = money(opening_balance_sheet.get("total_assets"))
    closing_assets = money(closing_balance_sheet.get("total_assets"))
    opening_equity = money(opening_balance_sheet.get("total_equity_including_current_earnings"))
    closing_equity = money(closing_balance_sheet.get("total_equity_including_current_earnings"))
    average_assets = money((opening_assets + closing_assets) / Decimal("2"))
    average_equity = money((opening_equity + closing_equity) / Decimal("2"))

    revenue = money(period_metrics.get("net_revenue"))
    gross_profit = money(period_metrics.get("gross_profit"))
    ebitda = money(period_metrics.get("ebitda"))
    ebit = money(period_metrics.get("ebit"))
    pat = money(period_metrics.get("pat"))
    interest = money(period_metrics.get("interest_expense"))
    debt = money(closing_balance_sheet.get("debt"))

    def multiple(numerator: Decimal, denominator: Decimal) -> Decimal | None:
        if denominator == 0:
            return None
        return (numerator / denominator).quantize(CENT, rounding=ROUND_HALF_UP)

    return {
        "gross_margin_pct": percentage(gross_profit, revenue),
        "ebitda_margin_pct": percentage(ebitda, revenue),
        "pat_margin_pct": percentage(pat, revenue),
        "operating_expense_ratio_pct": percentage(
            period_metrics.get("operating_expenses"), revenue
        ),
        "return_on_assets_pct": percentage(pat, average_assets),
        "return_on_equity_pct": percentage(pat, average_equity),
        "asset_turnover_x": multiple(revenue, average_assets),
        "debt_to_equity_x": multiple(debt, closing_equity),
        "interest_coverage_x": multiple(ebit, interest),
        "average_total_assets": average_assets,
        "average_equity": average_equity,
        "closing_debt": debt,
    }


def load_monthly_financial_trend(conn, organization_id: str, start_date: date, end_date: date) -> list[dict]:
    sql = """
    SELECT date_trunc('month', je.entry_date)::date AS month_start,
      COALESCE(SUM(CASE WHEN a.financial_category='revenue' THEN jl.credit-jl.debit ELSE 0 END),0) AS gross_sales,
      COALESCE(SUM(CASE WHEN a.financial_category='contra_revenue' THEN jl.debit-jl.credit ELSE 0 END),0) AS sales_returns,
      COALESCE(SUM(CASE WHEN a.financial_category='cogs' THEN jl.debit-jl.credit ELSE 0 END),0) AS cogs,
      COALESCE(SUM(CASE WHEN a.financial_category='operating_expense' THEN jl.debit-jl.credit ELSE 0 END),0) AS operating_expenses,
      COALESCE(SUM(CASE WHEN a.financial_category='depreciation' THEN jl.debit-jl.credit ELSE 0 END),0) AS depreciation,
      COALESCE(SUM(CASE WHEN a.financial_category='amortization' THEN jl.debit-jl.credit ELSE 0 END),0) AS amortization,
      COALESCE(SUM(CASE WHEN a.financial_category='interest_expense' THEN jl.debit-jl.credit ELSE 0 END),0) AS interest_expense,
      COALESCE(SUM(CASE WHEN a.financial_category='income_tax' THEN jl.debit-jl.credit ELSE 0 END),0) AS income_tax
    FROM journal_entries je
    JOIN journal_lines jl ON jl.organization_id=je.organization_id AND jl.journal_entry_id=je.id
    JOIN gl_accounts a ON a.organization_id=jl.organization_id AND a.id=jl.account_id
    WHERE je.organization_id=%s AND je.status='posted' AND je.entry_date BETWEEN %s AND %s
    GROUP BY 1 ORDER BY 1
    """
    rows = conn.execute(sql, (organization_id, start_date, end_date)).fetchall()
    result = []
    for row in rows:
        result.append({
            "month": str(row["month_start"]),
            **_as_float_dict(compute_financial_summary(row)),
        })
    return result


def load_budget_variance(conn, organization_id: str, period_start: date, period_end: date) -> list[dict]:
    budgets = conn.execute(
        """SELECT metric_code, budget_amount FROM budgets
           WHERE organization_id=%s AND period_start=%s AND period_end=%s
           ORDER BY metric_code""",
        (organization_id, period_start, period_end),
    ).fetchall()
    if not budgets:
        return []

    actuals = load_financial_summary(conn, organization_id, period_start, period_end)
    metric_map = {
        "net_revenue": ("net_revenue", "higher_is_better"),
        "gross_profit": ("gross_profit", "higher_is_better"),
        "ebitda": ("ebitda", "higher_is_better"),
        "pat": ("pat", "higher_is_better"),
        "operating_expense": ("operating_expenses", "lower_is_better"),
        "cogs": ("cogs", "lower_is_better"),
    }
    output = []
    for row in budgets:
        metric_code = row["metric_code"]
        if metric_code not in metric_map:
            output.append({"metric_code": metric_code, "budget": float(row["budget_amount"]), "actual": None,
                           "variance": None, "variance_pct": None, "favorable": None,
                           "note": "No actual calculation is configured for this budget metric."})
            continue
        actual_key, direction = metric_map[metric_code]
        budget = money(row["budget_amount"])
        actual = money(actuals[actual_key])
        variance = money(actual - budget)
        variance_pct = percentage(variance, budget)
        favorable = actual >= budget if direction == "higher_is_better" else actual <= budget
        output.append({
            "metric_code": metric_code,
            "budget": float(budget),
            "actual": float(actual),
            "variance": float(variance),
            "variance_pct": float(variance_pct) if variance_pct is not None else None,
            "favorable": favorable,
            "direction": direction,
        })
    return output
