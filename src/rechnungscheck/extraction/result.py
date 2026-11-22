"""Extractor output shared by all extractors."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from rechnungscheck.domain.invoice import Invoice


class ExtractionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice: Invoice
    extractor: str
    warnings: tuple[str, ...] = ()
