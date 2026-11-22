"""Structured extractor: the deterministic path for ZUGFeRD / Factur-X and XRechnung (UBL, CII).

Vision-LLM and prebuilt-Azure extractors (Phase 3/4) handle text PDFs and scans
behind the same ``ExtractionResult`` interface.
"""

from __future__ import annotations

from rechnungscheck.domain.invoice import SourceFormat
from rechnungscheck.extraction.cii import parse_cii
from rechnungscheck.extraction.result import ExtractionResult
from rechnungscheck.extraction.router import RoutedDocument
from rechnungscheck.extraction.ubl import parse_ubl

STRUCTURED_FORMATS = frozenset({SourceFormat.ZUGFERD, SourceFormat.XRECHNUNG_CII, SourceFormat.XRECHNUNG_UBL})


def extract_structured(doc: RoutedDocument, document_id: str) -> ExtractionResult:
    if doc.source_format is SourceFormat.XRECHNUNG_UBL:
        return parse_ubl(doc.data, document_id)
    if doc.source_format is SourceFormat.XRECHNUNG_CII:
        return parse_cii(doc.data, document_id)
    if doc.source_format is SourceFormat.ZUGFERD and doc.embedded_xml is not None:
        return parse_cii(
            doc.embedded_xml,
            document_id,
            source_format=SourceFormat.ZUGFERD,
            locator_prefix=f"{doc.embedded_xml_name}:",
        )
    raise ValueError(f"{doc.source_format} is not a structured format")
