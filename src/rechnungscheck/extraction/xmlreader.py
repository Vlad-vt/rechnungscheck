"""Typed value reading from XML with evidence (XPath) and parse warnings.

Values are returned as plain ``{"value", "confidence", "evidence"}`` dicts so
that the canonical model validates them against the exact field type (for
example a unit code pattern) when the invoice is assembled."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from lxml import etree
from pydantic import BaseModel, ValidationError

from rechnungscheck.domain.evidence import Evidence, EvidenceKind

Raw = dict[str, object]


class XmlReader:
    """Reads values relative to a context element; every value carries its XPath as evidence."""

    def __init__(
        self, root: etree._Element, ns: dict[str, str], evidence_prefix: str, locator_prefix: str = ""
    ) -> None:
        self.root = root
        self.tree = root.getroottree()
        self.ns = ns
        self.evidence_prefix = evidence_prefix
        self.locator_prefix = locator_prefix
        self.warnings: list[str] = []

    def all(self, ctx: etree._Element, xpath: str) -> list[etree._Element]:
        res = ctx.xpath(xpath, namespaces=self.ns)
        assert isinstance(res, list)  # noqa: S101
        return [e for e in res if isinstance(e, etree._Element)]

    def first(self, ctx: etree._Element, xpath: str) -> etree._Element | None:
        found = self.all(ctx, xpath)
        return found[0] if found else None

    def evidence(self, el: etree._Element, text: str | None = None) -> Evidence:
        path = self.tree.getpath(el)
        return Evidence(
            evidence_id=f"{self.evidence_prefix}:{path}",
            kind=EvidenceKind.XML,
            locator=f"{self.locator_prefix}{path}",
            text=(el.text or "").strip() if text is None else text,
        )

    def raw(self, value: object, el: etree._Element) -> Raw:
        return {"value": value, "confidence": 1.0, "evidence": (self.evidence(el),)}

    def _value(self, ctx: etree._Element, xpath: str, conv: Callable[[str], object]) -> Raw | None:
        el = self.first(ctx, xpath)
        if el is None or el.text is None or not el.text.strip():
            return None
        raw = el.text.strip()
        try:
            value = conv(raw)
            return self.raw(value, el)
        except (ValueError, InvalidOperation, ValidationError) as exc:
            self.warnings.append(f"{self.tree.getpath(el)}: cannot parse {raw!r} ({exc.__class__.__name__})")
            return None

    def text(self, ctx: etree._Element, xpath: str) -> Raw | None:
        return self._value(ctx, xpath, str)

    def decimal(self, ctx: etree._Element, xpath: str) -> Raw | None:
        def conv(s: str) -> Decimal:
            d = Decimal(s)
            if not d.is_finite():
                raise ValueError("non-finite")
            return d

        return self._value(ctx, xpath, conv)

    def date102(self, ctx: etree._Element, xpath: str) -> Raw | None:
        return self._value(ctx, xpath, lambda s: datetime.strptime(s, "%Y%m%d").date())  # noqa: DTZ007

    def iso_date(self, ctx: etree._Element, xpath: str) -> Raw | None:
        return self._value(ctx, xpath, date.fromisoformat)

    def validated[M: BaseModel](self, model: type[M], data: dict[str, object]) -> M:
        """Build a model, dropping fields that fail validation (and recording why)."""
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            bad = {str(e["loc"][0]) for e in exc.errors() if e["loc"]}
            self.warnings.append(f"{model.__name__}: dropped invalid fields {sorted(bad)}")
            return model.model_validate({k: v for k, v in data.items() if k not in bad})


_NOTE_RE = {
    "batch": re.compile(r"(?:Charge|Batch)\s*:\s*([^;]+)", re.IGNORECASE),
    "best_before": re.compile(r"(?:MHD|Best before)\s*:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    "serials": re.compile(r"(?:Seriennummern|Serial numbers)\s*:\s*([^;]+)", re.IGNORECASE),
}


def parse_line_note(reader: XmlReader, note_el: etree._Element | None) -> dict[str, Raw]:
    """Batch, best-before date and serial numbers from a line note (BT-127), if present."""
    out: dict[str, Raw] = {}
    if note_el is None or not note_el.text:
        return out
    text = note_el.text
    if m := _NOTE_RE["batch"].search(text):
        out["batch_number"] = reader.raw(m.group(1).strip(), note_el)
    if m := _NOTE_RE["best_before"].search(text):
        try:
            out["best_before_date"] = reader.raw(date.fromisoformat(m.group(1)), note_el)
        except ValueError:
            reader.warnings.append(f"line note: bad best-before date {m.group(1)!r}")
    if m := _NOTE_RE["serials"].search(text):
        sns = tuple(s.strip() for s in m.group(1).split(",") if s.strip())
        out["serial_numbers"] = reader.raw(sns, note_el)
    return out
