from datetime import date, datetime, timezone
from decimal import Decimal

from profitpulse.supply_chain import _json_value

import pytest

from profitpulse.supply_chain import (
    calculate_delay_days,
    calculate_otif,
    calculate_transit_days,
)


def test_transit_days_uses_departure_and_arrival_elapsed_time():
    departure = datetime(2026, 11, 1, 8, tzinfo=timezone.utc)
    arrival = datetime(2026, 11, 4, 20, tzinfo=timezone.utc)
    assert calculate_transit_days(departure, arrival) == 3.5


def test_transit_days_is_unknown_until_both_timestamps_exist():
    assert calculate_transit_days(None, None) is None
    assert calculate_transit_days(datetime.now(timezone.utc), None) is None


def test_transit_days_rejects_arrival_before_departure():
    departure = datetime(2026, 11, 4, tzinfo=timezone.utc)
    arrival = datetime(2026, 11, 3, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="before actual departure"):
        calculate_transit_days(departure, arrival)


def test_delay_days_returns_zero_for_on_time_or_early_arrival():
    promised = datetime(2026, 11, 6, 18, tzinfo=timezone.utc)
    actual = datetime(2026, 11, 5, 18, tzinfo=timezone.utc)
    assert calculate_delay_days(promised, actual) == 0


def test_delay_days_returns_whole_calendar_days_late():
    promised = datetime(2026, 11, 3, 18, tzinfo=timezone.utc)
    actual = datetime(2026, 11, 6, 9, tzinfo=timezone.utc)
    assert calculate_delay_days(promised, actual) == 3


def test_delay_days_is_unknown_without_eta_or_actual_date():
    assert calculate_delay_days(None, datetime.now(timezone.utc)) is None
    assert calculate_delay_days(datetime.now(timezone.utc), None) is None


def test_otif_requires_completed_po_to_be_on_time_and_fully_received():
    expected = date(2026, 11, 10)
    assert calculate_otif(expected, date(2026, 11, 9), Decimal("10"), Decimal("10")) is True
    assert calculate_otif(expected, date(2026, 11, 11), Decimal("10"), Decimal("10")) is False
    assert calculate_otif(expected, date(2026, 11, 9), Decimal("10"), Decimal("9")) is False


def test_otif_is_unknown_when_order_not_received():
    assert calculate_otif(date(2026, 11, 10), None, 10, 0) is None


def test_json_value_serializes_nested_decimal_and_dates():
    value = {
        "amount": Decimal("12.50"),
        "received_at": datetime(2026, 11, 6, 10, 30, tzinfo=timezone.utc),
        "items": [Decimal("2.25"), date(2026, 11, 7)],
    }
    result = _json_value(value)
    assert result["amount"] == 12.5
    assert result["received_at"] == "2026-11-06T10:30:00+00:00"
    assert result["items"] == [2.25, "2026-11-07"]


def test_otif_handles_decimal_precision_without_float_rounding():
    assert calculate_otif(
        date(2026, 11, 10), date(2026, 11, 10),
        Decimal("0.300"), Decimal("0.300")
    ) is True
    assert calculate_otif(
        date(2026, 11, 10), date(2026, 11, 10),
        Decimal("0.300"), Decimal("0.299")
    ) is False
