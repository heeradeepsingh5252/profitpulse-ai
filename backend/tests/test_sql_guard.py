import pytest

sqlglot = pytest.importorskip("sqlglot")
from profitpulse.sql_guard import UnsafeQueryError, validate_read_only_select


def test_select_is_limited():
    sql = validate_read_only_select("SELECT * FROM orders")
    assert "LIMIT 500" in sql.upper()


def test_delete_is_rejected():
    with pytest.raises(UnsafeQueryError):
        validate_read_only_select("DELETE FROM orders")


def test_multiple_statements_rejected():
    with pytest.raises(UnsafeQueryError):
        validate_read_only_select("SELECT 1; DROP TABLE orders")
