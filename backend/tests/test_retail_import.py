from decimal import Decimal

import pytest
from fastapi import HTTPException

from profitpulse.routers.retail import _csv_rows, _decimal


def test_sales_csv_headers_and_rows():
    raw = b"sale_date,sku,product_name,quantity,unit_price,unit_cost\n2026-11-01,S1,Shirt,2,100,40\n"
    rows = _csv_rows(raw, {"sale_date", "sku", "product_name", "quantity", "unit_price", "unit_cost"})
    assert len(rows) == 1
    assert rows[0][1]["sku"] == "S1"


def test_csv_header_is_case_and_whitespace_tolerant():
    raw = b" Sale_Date , SKU , Product_Name , Quantity , Unit_Price , Unit_Cost \n2026-11-01,S1,Shirt,2,100,40\n"
    rows = _csv_rows(raw, {"sale_date", "sku", "product_name", "quantity", "unit_price", "unit_cost"})
    assert rows[0][1]["product_name"] == "Shirt"


def test_csv_missing_columns_returns_validation_error():
    with pytest.raises(HTTPException) as error:
        _csv_rows(b"sku,product_name\nS1,Shirt\n", {"sale_date", "sku", "product_name"})
    assert error.value.status_code == 422


def test_decimal_parser_accepts_non_negative_values():
    assert _decimal("125.50", "unit_price", 2) == Decimal("125.50")


@pytest.mark.parametrize("value", ["-1", "NaN", "abc", ""])
def test_decimal_parser_rejects_invalid_values(value):
    with pytest.raises(HTTPException) as error:
        _decimal(value, "quantity", 2)
    assert error.value.status_code == 422
