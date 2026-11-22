"""Flatten a canonical invoice to ``{path: value}`` for field-level comparison (evals, tests).

Paths use explicit indices, e.g. ``lines[0].quantity`` or ``seller.address.city``;
evidence and confidence are dropped.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from rechnungscheck.domain.evidence import Extracted


def flatten_invoice(model: BaseModel, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in type(model).model_fields:
        if name in {"document_id", "source_format"} and not prefix:
            continue
        value = getattr(model, name)
        key = f"{prefix}{name}"
        if isinstance(value, Extracted):
            out[key] = value.value
        elif isinstance(value, BaseModel):
            out |= flatten_invoice(value, f"{key}.")
        elif isinstance(value, tuple):
            for i, item in enumerate(value):
                if isinstance(item, Extracted):
                    out[f"{key}[{i}]"] = item.value
                elif isinstance(item, BaseModel):
                    out |= flatten_invoice(item, f"{key}[{i}].")
        elif value is not None:
            out[key] = value
    return out
