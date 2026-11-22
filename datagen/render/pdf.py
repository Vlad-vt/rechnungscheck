"""Render invoices and delivery notes as PDFs (reportlab), plus ZUGFeRD hybrids (factur-x).

Output is deterministic (``invariant=1``). For PDF/A-3 (required for
ZUGFeRD) the renderer embeds the Bitstream Vera fonts shipped with reportlab and
adds an sRGB OutputIntent; factur-x then writes the PDF/A-3 XMP metadata and
attaches the XML. Conformance is checked by Mustang's veraPDF (ADR 0003).
"""

from __future__ import annotations

import io
from datetime import date, datetime, tzinfo
from decimal import Decimal

from PIL import ImageCms
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from datagen.render.common import UNIT_LABEL, amount, dec, number, price, txt, v
from rechnungscheck.domain.invoice import Invoice
from rechnungscheck.domain.orders import DeliveryNote

W, H = A4

pdfmetrics.registerFont(TTFont("Vera", "Vera.ttf"))
pdfmetrics.registerFont(TTFont("VeraBd", "VeraBd.ttf"))
FONT, FONT_BOLD = "Vera", "VeraBd"

L = {
    "de": {
        "invoice": "Rechnung",
        "no": "Rechnungsnummer",
        "date": "Rechnungsdatum",
        "po": "Bestellnummer",
        "dn": "Lieferschein",
        "delivery": "Lieferdatum",
        "buyer_ref": "Ihre Referenz",
        "pos": "Pos",
        "item": "Bezeichnung",
        "qty": "Menge",
        "unit": "Einheit",
        "price": "Einzelpreis",
        "vat": "USt %",
        "net": "Betrag",
        "sum_net": "Summe netto",
        "vat_amt": "USt",
        "gross": "Gesamtbetrag",
        "due": "Fällig am",
        "bank": "Bankverbindung",
        "vat_id": "USt-IdNr.",
        "per": "je",
        "notes": "Hinweise",
        "batch": "Charge",
        "bb": "MHD",
        "sn": "SN",
        "dn_title": "Lieferschein",
        "dn_no": "Lieferscheinnummer",
        "contact": "Ansprechpartner",
    },
    "en": {
        "invoice": "Invoice",
        "no": "Invoice number",
        "date": "Invoice date",
        "po": "Purchase order",
        "dn": "Delivery note",
        "delivery": "Delivery date",
        "buyer_ref": "Your reference",
        "pos": "Pos",
        "item": "Description",
        "qty": "Qty",
        "unit": "Unit",
        "price": "Unit price",
        "vat": "VAT %",
        "net": "Amount",
        "sum_net": "Net total",
        "vat_amt": "VAT",
        "gross": "Total amount",
        "due": "Due date",
        "bank": "Bank details",
        "vat_id": "VAT ID",
        "per": "per",
        "notes": "Notes",
        "batch": "Batch",
        "bb": "Best before",
        "sn": "SN",
        "dn_title": "Delivery note",
        "dn_no": "Delivery note number",
        "contact": "Contact",
    },
}


def _de_num(s: str, lang: str) -> str:
    """German number formatting: 1234.5 -> 1.234,5"""
    if lang != "de":
        return s
    whole, _, frac = s.partition(".")
    neg = whole.startswith("-")
    whole = whole.lstrip("-")
    groups: list[str] = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    out = ("-" if neg else "") + ".".join(groups)
    return out + ("," + frac if frac else "")


def _d(d: date | None, lang: str) -> str:
    if d is None:
        return ""
    return d.strftime("%d.%m.%Y") if lang == "de" else d.isoformat()


class _Page:
    def __init__(self) -> None:
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4, invariant=1, pageCompression=1)
        self.y = H - 20 * mm

    def text(self, x: float, s: str, size: float = 9, bold: bool = False, y: float | None = None) -> None:
        self.c.setFont(FONT_BOLD if bold else FONT, size)
        self.c.drawString(x, self.y if y is None else y, s)

    def right(self, x: float, s: str, size: float = 9, bold: bool = False) -> None:
        self.c.setFont(FONT_BOLD if bold else FONT, size)
        self.c.drawRightString(x, self.y, s)

    def down(self, step: float = 4.6 * mm) -> None:
        self.y -= step
        if self.y < 25 * mm:
            self.c.showPage()
            self.y = H - 20 * mm

    def finish(self) -> bytes:
        self.c.showPage()
        self.c.save()
        return add_srgb_output_intent(self.buf.getvalue())


def _deterministic_srgb_icc() -> bytes:
    """LittleCMS sRGB profile with a fixed creation date and a zeroed profile id (bytes 84-99),
    so that rendered PDFs are byte-identical across runs."""
    icc = bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    icc[24:36] = bytes([0x07, 0xEA, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0])  # 2026-01-01 00:00:00
    icc[84:100] = bytes(16)
    return bytes(icc)


_SRGB_ICC = _deterministic_srgb_icc()


def add_srgb_output_intent(pdf: bytes) -> bytes:
    """PDF/A needs an OutputIntent when device colour spaces are used."""
    writer = PdfWriter(clone_from=io.BytesIO(pdf))
    icc = DecodedStreamObject()
    icc.set_data(_SRGB_ICC)
    icc[NameObject("/N")] = NumberObject(3)
    intent = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/OutputIntent"),
            NameObject("/S"): NameObject("/GTS_PDFA1"),
            NameObject("/OutputConditionIdentifier"): TextStringObject("sRGB"),
            NameObject("/Info"): TextStringObject("sRGB IEC61966-2.1"),
            NameObject("/DestOutputProfile"): writer._add_object(icc),
        }
    )
    writer._root_object[NameObject("/OutputIntents")] = ArrayObject([writer._add_object(intent)])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def render_invoice_pdf(inv: Invoice, lang: str, hidden_text: str | None = None) -> bytes:
    t = L[lang]
    p = _Page()
    s = inv.seller
    # letterhead
    p.text(20 * mm, txt(s.name), 14, bold=True)
    p.down(6 * mm)
    if s.address:
        p.text(
            20 * mm,
            f"{txt(s.address.street)} · {txt(s.address.post_code)} {txt(s.address.city)}",
            8,
        )
        p.down()
    contact = " · ".join(x for x in (v(s.contact_name), v(s.contact_phone), v(s.contact_email)) if x)
    if contact:
        p.text(20 * mm, f"{t['contact']}: {contact}", 8)
        p.down()
    if s.vat_id:
        p.text(20 * mm, f"{t['vat_id']}: {s.vat_id.value}", 8)
    p.down(10 * mm)
    # buyer block
    b = inv.buyer
    p.text(20 * mm, txt(b.name), 10)
    p.down()
    if b.address:
        p.text(20 * mm, txt(b.address.street), 10)
        p.down()
        p.text(20 * mm, f"{txt(b.address.post_code)} {txt(b.address.city)}", 10)
    p.down(12 * mm)
    p.text(20 * mm, t["invoice"], 16, bold=True)
    p.down(8 * mm)
    meta = [
        (t["no"], v(inv.invoice_number)),
        (t["date"], _d(v(inv.issue_date), lang)),
        (t["po"], v(inv.order_reference)),
        (t["dn"], v(inv.despatch_advice_reference)),
        (t["delivery"], _d(v(inv.delivery_date), lang)),
        (t["buyer_ref"], v(inv.buyer_reference)),
    ]
    for label, value in meta:
        if value:
            p.text(20 * mm, f"{label}:", 9)
            p.text(60 * mm, str(value), 9)
            p.down()
    p.down(4 * mm)
    # table header
    cols = (20 * mm, 30 * mm, 120 * mm, 133 * mm, 158 * mm, 172 * mm, 190 * mm)
    p.text(cols[0], t["pos"], 8, bold=True)
    p.text(cols[1], t["item"], 8, bold=True)
    p.right(cols[2] + 8 * mm, t["qty"], 8, bold=True)
    p.text(cols[3] - 3 * mm, t["unit"], 8, bold=True)
    p.right(cols[4] + 4 * mm, t["price"], 8, bold=True)
    p.right(cols[5] + 2 * mm, t["vat"], 8, bold=True)
    p.right(cols[6], t["net"], 8, bold=True)
    p.down()
    p.c.line(20 * mm, p.y + 3 * mm, 190 * mm, p.y + 3 * mm)
    for line in inv.lines:
        unit = v(line.unit_code) or "C62"
        base = dec(line.price_base_quantity) if line.price_base_quantity else Decimal(1)
        unit_label = UNIT_LABEL[lang].get(unit, unit)
        price_txt = _de_num(price(dec(line.net_price)), lang)
        if base != 1:
            price_txt += f" {t['per']} {_de_num(number(base), lang)}"
        p.text(cols[0], txt(line.line_id), 8)
        p.text(cols[1], (txt(line.item_name))[:48], 8)
        p.right(cols[2] + 8 * mm, _de_num(number(dec(line.quantity)), lang), 8)
        p.text(cols[3] - 3 * mm, unit_label, 8)
        p.right(cols[4] + 4 * mm, price_txt, 8)
        p.right(cols[5] + 2 * mm, _de_num(number(dec(line.vat_rate)), lang), 8)
        p.right(cols[6], _de_num(amount(dec(line.line_net_amount)), lang), 8)
        p.down(4 * mm)
        detail = []
        if line.seller_item_id:
            detail.append(f"Art. {line.seller_item_id.value}")
        if line.gtin:
            detail.append(f"GTIN {line.gtin.value}")
        if line.batch_number:
            detail.append(f"{t['batch']} {line.batch_number.value}")
        if line.best_before_date:
            detail.append(f"{t['bb']} {_d(line.best_before_date.value, lang)}")
        if detail:
            p.text(cols[1], " · ".join(detail), 7)
            p.down(3.6 * mm)
        if line.serial_numbers:
            sns = list(line.serial_numbers.value)
            for k in range(0, len(sns), 4):
                p.text(cols[1], f"{t['sn']}: " + ", ".join(sns[k : k + 4]), 7)
                p.down(3.6 * mm)
        p.down(1.2 * mm)
    p.c.line(20 * mm, p.y + 3 * mm, 190 * mm, p.y + 3 * mm)
    p.down(2 * mm)
    tot = inv.totals
    p.text(130 * mm, t["sum_net"], 9)
    p.right(190 * mm, _de_num(amount(dec(tot.total_without_vat)), lang) + " EUR", 9)
    p.down()
    for vb in inv.vat_breakdown:
        rate = _de_num(number(dec(vb.rate)), lang)
        base_txt = _de_num(amount(dec(vb.taxable_amount)), lang)
        p.text(130 * mm, f"{t['vat_amt']} {rate} % ({base_txt})", 9)
        p.right(190 * mm, _de_num(amount(dec(vb.tax_amount)), lang) + " EUR", 9)
        p.down()
    p.text(130 * mm, t["gross"], 10, bold=True)
    p.right(190 * mm, _de_num(amount(dec(tot.total_with_vat)), lang) + " EUR", 10, bold=True)
    p.down(10 * mm)
    if inv.payment.terms:
        p.text(20 * mm, inv.payment.terms.value, 9)
        p.down()
    if inv.due_date:
        p.text(20 * mm, f"{t['due']}: {_d(inv.due_date.value, lang)}", 9)
        p.down()
    if inv.payment.iban:
        bic = f" · BIC {inv.payment.bic.value}" if inv.payment.bic else ""
        p.text(20 * mm, f"{t['bank']}: IBAN {inv.payment.iban.value}{bic}", 9)
        p.down()
    if inv.notes:
        p.down(3 * mm)
        p.text(20 * mm, t["notes"] + ":", 9, bold=True)
        p.down()
        for n in inv.notes:
            for chunk in _wrap(n.value, 105):
                p.text(20 * mm, chunk, 8)
                p.down(4 * mm)
    if hidden_text:
        # Invisible to a human reader (white, 1 pt) but present in the text layer.
        p.c.setFillColorRGB(1, 1, 1)
        p.c.setFont(FONT, 1)
        p.c.drawString(20 * mm, 12 * mm, hidden_text)
        p.c.setFillColorRGB(0, 0, 0)
    return p.finish()


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def render_delivery_note_pdf(dn: DeliveryNote, supplier_name: str, buyer_name: str, lang: str) -> bytes:
    t = L[lang]
    p = _Page()
    p.text(20 * mm, supplier_name, 14, bold=True)
    p.down(10 * mm)
    p.text(20 * mm, buyer_name, 10)
    p.down(12 * mm)
    p.text(20 * mm, t["dn_title"], 16, bold=True)
    p.down(8 * mm)
    for label, value in (
        (t["dn_no"], dn.dn_number),
        (t["po"], dn.po_number),
        (t["delivery"], _d(dn.delivery_date, lang)),
    ):
        p.text(20 * mm, f"{label}:", 9)
        p.text(60 * mm, value, 9)
        p.down()
    p.down(4 * mm)
    p.text(20 * mm, t["pos"], 8, bold=True)
    p.text(30 * mm, t["item"], 8, bold=True)
    p.right(150 * mm, t["qty"], 8, bold=True)
    p.text(155 * mm, t["unit"], 8, bold=True)
    p.down()
    for ln in dn.lines:
        p.text(20 * mm, str(ln.line_no), 8)
        p.text(30 * mm, ln.description[:60], 8)
        p.right(150 * mm, _de_num(number(ln.quantity), lang), 8)
        p.text(155 * mm, UNIT_LABEL[lang].get(ln.unit_code, ln.unit_code), 8)
        p.down(4 * mm)
        detail = [f"GTIN {ln.gtin}"]
        if ln.batch_number:
            detail.append(f"{t['batch']} {ln.batch_number}")
        if ln.best_before_date:
            detail.append(f"{t['bb']} {_d(ln.best_before_date, lang)}")
        p.text(30 * mm, " · ".join(detail), 7)
        p.down(3.6 * mm)
        for k in range(0, len(ln.serial_numbers), 4):
            p.text(30 * mm, f"{t['sn']}: " + ", ".join(ln.serial_numbers[k : k + 4]), 7)
            p.down(3.6 * mm)
        p.down(1.2 * mm)
    return p.finish()


def make_zugferd(pdf: bytes, cii_xml: bytes, timestamp: datetime) -> bytes:
    """Attach the Factur-X XML. factur-x stamps XMP and file dates with ``datetime.now()``;
    the clock is pinned to ``timestamp`` so the output is reproducible."""
    import facturx  # noqa: PLC0415
    from facturx import facturx as fx_module  # noqa: PLC0415

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> _FrozenDatetime:
            return cls.fromtimestamp(timestamp.timestamp(), tz)

    real = fx_module.datetime
    fx_module.datetime = _FrozenDatetime
    try:
        out = facturx.generate_from_binary(
            pdf, cii_xml, flavor="factur-x", level="en16931", check_xsd=True, lang="de-DE"
        )
    finally:
        fx_module.datetime = real
    return bytes(out)
