"""Helpers shared by the renderers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from rechnungscheck.domain.evidence import Extracted
from rechnungscheck.domain.invoice import InvoiceLine

XRECHNUNG_ID = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
EN16931_ID = "urn:cen.eu:en16931:2017"  # Factur-X / ZUGFeRD 2.x profile EN 16931
PEPPOL_PROCESS = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

UNIT_LABEL = {
    "de": {"C62": "Stk", "KGM": "kg", "XCT": "Karton"},
    "en": {"C62": "pcs", "KGM": "kg", "XCT": "carton"},
}


def v[V](e: Extracted[V] | None) -> V | None:
    return None if e is None else e.value


def amount(d: Decimal) -> str:
    """Monetary amount with exactly two decimals."""
    return f"{d.quantize(Decimal('0.01')):f}"


def number(d: Decimal) -> str:
    """Quantity or price: no exponent, trailing zeros removed, at least one digit."""
    s = f"{d.normalize():f}"
    return s if "." not in s else s.rstrip("0").rstrip(".") or "0"


def price(d: Decimal) -> str:
    s = number(d)
    if "." not in s:
        return s + ".00"
    whole, frac = s.split(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def line_note(line: InvoiceLine, lang: str) -> str | None:
    """Batch, best-before and serial numbers as an EN 16931 line note (BT-127).

    EN 16931 has no business terms for them; suppliers commonly put them in the
    line note. Parsers read them back from this exact format."""
    parts: list[str] = []
    batch, bb, serials = v(line.batch_number), v(line.best_before_date), v(line.serial_numbers)
    if batch:
        parts.append(f"{'Charge' if lang == 'de' else 'Batch'}: {batch}")
    if bb:
        parts.append(f"{'MHD' if lang == 'de' else 'Best before'}: {bb.isoformat()}")
    if serials:
        parts.append(f"{'Seriennummern' if lang == 'de' else 'Serial numbers'}: {', '.join(serials)}")
    return "; ".join(parts) or None


def dec(e: Extracted[Decimal] | None) -> Decimal:
    return Decimal(0) if e is None else e.value


def txt(e: Extracted[str] | None) -> str:
    return "" if e is None else e.value
