from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from rechnungscheck.domain import (
    INVOICE_FIELD_PATHS,
    Evidence,
    EvidenceKind,
    Extracted,
    Invoice,
    InvoiceLine,
    SourceFormat,
    VatCategory,
)


def _xml(eid: str, xpath: str, text: str) -> Evidence:
    return Evidence(evidence_id=eid, kind=EvidenceKind.XML, locator=xpath, text=text)


def test_minimal_invoice_is_valid_because_extraction_may_be_incomplete():
    inv = Invoice(document_id="doc-1", source_format=SourceFormat.SCAN)
    assert inv.invoice_number is None
    assert inv.lines == ()


def test_full_line_round_trips_through_json():
    line = InvoiceLine(
        line_id=Extracted(value="1", confidence=1.0, evidence=(_xml("e1", "/x/ID", "1"),)),
        quantity=Extracted(value=Decimal("12.000"), confidence=1.0),
        unit_code=Extracted(value="C62", confidence=1.0),
        net_price=Extracted(value=Decimal("1.20"), confidence=1.0),
        vat_category=Extracted(value=VatCategory.STANDARD, confidence=1.0),
        vat_rate=Extracted(value=Decimal("7"), confidence=1.0),
        best_before_date=Extracted(value=date(2026, 12, 31), confidence=0.9),
        serial_numbers=Extracted(value=("SN-1", "SN-2"), confidence=0.8),
    )
    inv = Invoice(document_id="doc-2", source_format=SourceFormat.ZUGFERD, lines=(line,))
    again = Invoice.model_validate_json(inv.model_dump_json())
    assert again == inv
    assert again.lines[0].quantity is not None
    assert again.lines[0].quantity.value == Decimal("12.000")


def test_amounts_are_decimals_not_floats():
    e = Extracted[Decimal].model_validate({"value": "20.71", "confidence": 1})
    assert isinstance(e.value, Decimal)
    assert e.value == Decimal("20.71")


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_amounts_are_rejected(bad):
    with pytest.raises(ValidationError):
        InvoiceLine.model_validate({"net_price": {"value": bad, "confidence": 1}})


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_must_be_between_zero_and_one(confidence):
    with pytest.raises(ValidationError):
        Extracted(value="x", confidence=confidence)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        Invoice.model_validate({"document_id": "d", "source_format": "scan", "approved": True})


def test_models_are_immutable():
    inv = Invoice(document_id="d", source_format=SourceFormat.SCAN)
    with pytest.raises(ValidationError):
        inv.document_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [("currency", "eur"), ("currency", "EURO")],
)
def test_currency_code_format(field, value):
    with pytest.raises(ValidationError):
        Invoice.model_validate(
            {"document_id": "d", "source_format": "scan", field: {"value": value, "confidence": 1}}
        )


def test_unit_code_format():
    with pytest.raises(ValidationError):
        InvoiceLine.model_validate({"unit_code": {"value": "piece", "confidence": 1}})


def test_field_paths_cover_header_nested_and_line_fields():
    assert {
        "invoice_number",
        "buyer_reference",
        "seller.vat_id",
        "seller.address.country_code",
        "payment.iban",
        "totals.total_with_vat",
        "lines[].batch_number",
        "lines[].serial_numbers",
        "vat_breakdown[].rate",
    } <= INVOICE_FIELD_PATHS
    assert "document_id" not in INVOICE_FIELD_PATHS
    assert "lines" not in INVOICE_FIELD_PATHS


def test_every_field_carries_its_business_term_id():
    schema = Invoice.model_json_schema()
    for name, prop in schema["properties"].items():
        if name in {
            "document_id",
            "source_format",
            "notes",
            "seller",
            "buyer",
            "payment",
            "lines",
            "vat_breakdown",
            "totals",
        }:
            continue
        assert "bt" in prop, name
