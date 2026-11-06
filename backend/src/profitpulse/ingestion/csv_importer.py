import csv
import io
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class CustomerRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    customer_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    region: str | None = None
    customer_type: str = "retail"

    @field_validator("customer_type")
    @classmethod
    def valid_customer_type(cls, value: str) -> str:
        if value not in {"retail", "wholesale", "b2b", "other"}:
            raise ValueError("customer_type must be retail, wholesale, b2b or other")
        return value


class ProductRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    sku: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    unit_price: Decimal = Field(ge=0)
    unit_cost: Decimal = Field(ge=0)
    reorder_level: int = Field(default=0, ge=0)
    unit_of_measure: str = "unit"


def parse_csv(content: bytes, entity: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Parse a UTF-8 CSV and return (valid rows, validation errors, row count)."""
    if entity not in {"customers", "products"}:
        raise ValueError("Supported import entities are customers and products")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    required = {
        "customers": {"customer_code", "name"},
        "products": {"sku", "name", "category", "unit_price", "unit_cost"},
    }[entity]
    headers = set(reader.fieldnames or [])
    missing = required - headers
    if missing:
        raise ValueError("Missing required CSV columns: " + ", ".join(sorted(missing)))

    model = CustomerRow if entity == "customers" else ProductRow
    accepted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    total = 0
    for row_number, raw in enumerate(reader, start=2):
        total += 1
        raw = {key: (value if value not in (None, "") else None) for key, value in raw.items()}
        try:
            clean = model.model_validate(raw).model_dump()
            clean["_row_number"] = row_number
            accepted.append(clean)
        except ValidationError as exc:
            errors.append({"row_number": row_number, "error_message": str(exc), "raw_row": raw})
    return accepted, errors, total
