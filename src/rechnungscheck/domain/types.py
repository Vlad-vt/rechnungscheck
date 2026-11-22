"""Constrained scalar types used across the domain models."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def _finite(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("decimal value must be finite")
    return value


Amount = Annotated[Decimal, AfterValidator(_finite)]
"""Monetary amount in the document currency. Never a float."""

Quantity = Annotated[Decimal, AfterValidator(_finite)]
"""Quantity in the given unit of measure. Never a float."""

Percent = Annotated[Decimal, AfterValidator(_finite)]
"""Percentage value as written on invoices, e.g. ``19`` for 19 %."""

CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
"""ISO 4217 alpha-3 currency code."""

CountryCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
"""ISO 3166-1 alpha-2 country code."""

UnitCode = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]{2,3}$")]
"""UN/ECE Recommendation 20 / 21 unit code, e.g. ``C62`` (piece), ``KGM`` (kilogram), ``XCT`` (carton)."""
