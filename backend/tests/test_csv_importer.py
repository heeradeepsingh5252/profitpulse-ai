import pytest

from profitpulse.ingestion.csv_importer import parse_csv


def test_customer_csv_parses_valid_rows():
    content = b"customer_code,name,email,city,customer_type\nC-001,Asha,asha@example.test,Hyderabad,retail\n"
    accepted, errors, total = parse_csv(content, "customers")
    assert total == 1
    assert len(accepted) == 1
    assert errors == []
    assert accepted[0]["customer_code"] == "C-001"


def test_product_csv_rejects_negative_price():
    content = b"sku,name,category,unit_price,unit_cost\nP-001,Item,Office,-10,5\n"
    accepted, errors, total = parse_csv(content, "products")
    assert total == 1
    assert accepted == []
    assert len(errors) == 1


def test_csv_requires_columns():
    with pytest.raises(ValueError, match="Missing required CSV columns"):
        parse_csv(b"name\nAsha\n", "customers")


def test_unsupported_entity_rejected():
    with pytest.raises(ValueError, match="Supported import entities"):
        parse_csv(b"a\nb\n", "orders")
