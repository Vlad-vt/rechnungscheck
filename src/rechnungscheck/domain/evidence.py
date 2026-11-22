"""Evidence and confidence attached to every extracted value.

Every figure that later appears in a decision or a supplier email must trace
back to an ``Evidence`` item. The Fact Checker enforces this by evidence id.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvidenceKind(StrEnum):
    """Where a value was read from."""

    XML = "xml"
    """Embedded or standalone XML (ZUGFeRD / Factur-X / XRechnung). Locator is an XPath."""
    PDF_TEXT = "pdf_text"
    """Text layer of a PDF. Locator names the page and the text span."""
    IMAGE_REGION = "image_region"
    """Region of a rendered page or scan, read by a vision model or OCR."""
    MASTER_DATA = "master_data"
    """Tenant master data (purchase order, delivery note, supplier, product)."""
    DERIVED = "derived"
    """Computed by code from other evidence, e.g. a line total recomputed from quantity and price."""


BBox = tuple[float, float, float, float]
"""Bounding box ``(x0, y0, x1, y1)`` in page coordinates, origin top left, normalised to 0..1."""


class Evidence(BaseModel):
    """One piece of evidence for a value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1, description="Stable id, unique within one case.")
    kind: EvidenceKind
    locator: str = Field(min_length=1, description="XPath, page/span reference or master-data key.")
    page: int | None = Field(default=None, ge=1)
    bbox: BBox | None = None
    text: str | None = Field(
        default=None,
        description="Raw text as found in the source. Untrusted input: never executed or obeyed.",
    )
    derived_from: tuple[str, ...] = Field(
        default=(), description="Evidence ids this value was computed from (kind=derived only)."
    )


class Extracted[T](BaseModel):
    """A value together with the extractor's confidence and its evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: T
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[Evidence, ...] = ()
