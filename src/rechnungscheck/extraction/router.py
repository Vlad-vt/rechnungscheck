"""Format Router (node 1): decides the source format by inspecting the bytes. Plain code, no LLM.

* XML: root element decides UBL vs CII. ``xrechnung_cii`` covers any standalone CII
  invoice; whether it claims the XRechnung CIUS is the Compliance Checker's job.
* PDF with an embedded Factur-X / ZUGFeRD / XRechnung XML attachment: ``zugferd``.
* PDF with a usable text layer: ``text_pdf``. Otherwise: ``scan``.
* PNG / JPEG / TIFF: ``scan``.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from rechnungscheck.domain.invoice import SourceFormat
from rechnungscheck.extraction import cii, ubl
from rechnungscheck.extraction.xmlsafe import UnsafeXmlError, parse_xml

# Attachment names used by Factur-X 1.x / ZUGFeRD 2.x, ZUGFeRD 1.x and XRechnung-in-PDF.
EMBEDDED_XML_NAMES = ("factur-x.xml", "zugferd-invoice.xml", "ZUGFeRD-invoice.xml", "xrechnung.xml")
MIN_TEXT_CHARS = 80
MAX_PDF_BYTES = 30 * 1024 * 1024
_IMAGE_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*")


class UnsupportedDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class RoutedDocument:
    source_format: SourceFormat
    data: bytes
    embedded_xml: bytes | None = None
    embedded_xml_name: str | None = None
    pdf_text: str | None = None


def embedded_invoice_xml(pdf: bytes) -> tuple[str, bytes] | None:
    reader = PdfReader(io.BytesIO(pdf))
    attachments = reader.attachments
    for name in EMBEDDED_XML_NAMES:
        if attachments.get(name):
            return name, attachments[name][0]
    return None


def route(data: bytes) -> RoutedDocument:
    head = data[:16].lstrip()
    if head.startswith(b"%PDF"):
        if len(data) > MAX_PDF_BYTES:
            raise UnsupportedDocumentError("PDF too large")
        try:
            found = embedded_invoice_xml(data)
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:3])
        except PdfReadError as exc:
            raise UnsupportedDocumentError(f"unreadable PDF: {exc}") from exc
        if found:
            return RoutedDocument(SourceFormat.ZUGFERD, data, found[1], found[0], text)
        if len(text.strip()) >= MIN_TEXT_CHARS:
            return RoutedDocument(SourceFormat.TEXT_PDF, data, pdf_text=text)
        return RoutedDocument(SourceFormat.SCAN, data)
    if any(data.startswith(m) for m in _IMAGE_MAGIC):
        return RoutedDocument(SourceFormat.SCAN, data)
    if head.startswith((b"<?xml", b"<", b"\xef\xbb\xbf")):
        try:
            root = parse_xml(data)
        except UnsafeXmlError:
            raise
        except Exception as exc:
            raise UnsupportedDocumentError(f"malformed XML: {exc}") from exc
        if root.tag == cii.ROOT_TAG:
            return RoutedDocument(SourceFormat.XRECHNUNG_CII, data)
        if root.tag == ubl.ROOT_TAG:
            return RoutedDocument(SourceFormat.XRECHNUNG_UBL, data)
        raise UnsupportedDocumentError(f"unknown XML root element {root.tag}")
    raise UnsupportedDocumentError("unknown document type")
