"""Canonical invoice model: a subset of EN 16931 with per-field evidence.

Every extractor (structured XML parser, vision LLM, prebuilt Azure model)
produces this model, so that compliance checks, matching and evals do not
care where an invoice came from.

Design rules:

* The model records what was extracted, not what is valid. Almost every field
  is optional, because a degraded scan may lack an invoice number. Whether a
  field is mandatory is decided by the Compliance Checker from EN 16931 rules
  and the tenant's ``mandatory_fields``.
* No arithmetic and no business rules live here. Totals are stored as found,
  never recomputed in the model.
* Each field carries its EN 16931 business term id (``bt``) in the JSON
  schema, so that rule violations and evidence can name it.
* Batch, best-before date and serial numbers are not EN 16931 core terms.
  They are extensions (as in ZUGFeRD EXTENDED and on delivery notes) and are
  marked ``bt: "EXT"``.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from rechnungscheck.domain.evidence import Extracted
from rechnungscheck.domain.types import Amount, CountryCode, CurrencyCode, Percent, Quantity, UnitCode


def _bt(term: str, description: str) -> Any:  # noqa: ANN401 - pydantic FieldInfo factory
    return Field(default=None, description=f"{term} {description}", json_schema_extra={"bt": term})


class SourceFormat(StrEnum):
    """Result of the Format Router."""

    ZUGFERD = "zugferd"
    """ZUGFeRD / Factur-X hybrid: PDF with embedded CII XML."""
    XRECHNUNG_UBL = "xrechnung_ubl"
    XRECHNUNG_CII = "xrechnung_cii"
    TEXT_PDF = "text_pdf"
    SCAN = "scan"


class InvoiceTypeCode(StrEnum):
    """UNTDID 1001 subset relevant here (BT-3)."""

    COMMERCIAL_INVOICE = "380"
    CREDIT_NOTE = "381"
    CORRECTED_INVOICE = "384"
    PREPAYMENT_INVOICE = "386"
    SELF_BILLED_INVOICE = "389"


class VatCategory(StrEnum):
    """UNCL 5305 VAT category codes used by EN 16931 (BT-118 / BT-151)."""

    STANDARD = "S"
    ZERO_RATED = "Z"
    EXEMPT = "E"
    REVERSE_CHARGE = "AE"
    INTRA_COMMUNITY = "K"
    EXPORT = "G"
    NOT_SUBJECT = "O"
    CANARY_ISLANDS = "L"
    CEUTA_MELILLA = "M"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PostalAddress(_Model):
    """BG-5 (seller) / BG-8 (buyer)."""

    street: Extracted[str] | None = _bt("BT-35/BT-50", "Address line 1")
    city: Extracted[str] | None = _bt("BT-37/BT-52", "City")
    post_code: Extracted[str] | None = _bt("BT-38/BT-53", "Post code")
    country_code: Extracted[CountryCode] | None = _bt("BT-40/BT-55", "Country code")


class Party(_Model):
    """BG-4 seller / BG-7 buyer."""

    name: Extracted[str] | None = _bt("BT-27/BT-44", "Name")
    vat_id: Extracted[str] | None = _bt("BT-31/BT-48", "VAT identifier")
    tax_number: Extracted[str] | None = _bt("BT-32", "Tax registration identifier (seller only)")
    address: PostalAddress | None = None


class PaymentInstructions(_Model):
    """BG-16 payment instructions and BT-20 payment terms."""

    means_code: Extracted[str] | None = _bt("BT-81", "Payment means type code (UNTDID 4461)")
    iban: Extracted[str] | None = _bt("BT-84", "Payment account identifier (IBAN)")
    account_name: Extracted[str] | None = _bt("BT-85", "Payment account name")
    bic: Extracted[str] | None = _bt("BT-86", "Payment service provider identifier (BIC)")
    terms: Extracted[str] | None = _bt("BT-20", "Payment terms")


class InvoiceLine(_Model):
    """BG-25 invoice line."""

    line_id: Extracted[str] | None = _bt("BT-126", "Invoice line identifier")
    order_line_reference: Extracted[str] | None = _bt("BT-132", "Referenced purchase order line")
    item_name: Extracted[str] | None = _bt("BT-153", "Item name")
    seller_item_id: Extracted[str] | None = _bt("BT-155", "Item seller's identifier")
    buyer_item_id: Extracted[str] | None = _bt("BT-156", "Item buyer's identifier")
    gtin: Extracted[str] | None = _bt("BT-157", "Item standard identifier (GTIN, scheme 0160)")
    quantity: Extracted[Quantity] | None = _bt("BT-129", "Invoiced quantity")
    unit_code: Extracted[UnitCode] | None = _bt("BT-130", "Invoiced quantity unit of measure code")
    net_price: Extracted[Amount] | None = _bt("BT-146", "Item net price")
    price_base_quantity: Extracted[Quantity] | None = _bt("BT-149", "Item price base quantity")
    line_net_amount: Extracted[Amount] | None = _bt("BT-131", "Invoice line net amount")
    vat_category: Extracted[VatCategory] | None = _bt("BT-151", "Invoiced item VAT category code")
    vat_rate: Extracted[Percent] | None = _bt("BT-152", "Invoiced item VAT rate")
    batch_number: Extracted[str] | None = _bt("EXT", "Batch / lot number")
    best_before_date: Extracted[date] | None = _bt("EXT", "Best-before date")
    serial_numbers: Extracted[tuple[str, ...]] | None = _bt("EXT", "Serial numbers")


class VatBreakdown(_Model):
    """BG-23 VAT breakdown, one per category and rate."""

    category: Extracted[VatCategory] | None = _bt("BT-118", "VAT category code")
    rate: Extracted[Percent] | None = _bt("BT-119", "VAT category rate")
    taxable_amount: Extracted[Amount] | None = _bt("BT-116", "VAT category taxable amount")
    tax_amount: Extracted[Amount] | None = _bt("BT-117", "VAT category tax amount")
    exemption_reason: Extracted[str] | None = _bt("BT-120", "VAT exemption reason text")


class DocumentTotals(_Model):
    """BG-22 document totals, stored as found on the document."""

    sum_of_line_net: Extracted[Amount] | None = _bt("BT-106", "Sum of invoice line net amount")
    allowances: Extracted[Amount] | None = _bt("BT-107", "Sum of allowances on document level")
    charges: Extracted[Amount] | None = _bt("BT-108", "Sum of charges on document level")
    total_without_vat: Extracted[Amount] | None = _bt("BT-109", "Invoice total amount without VAT")
    total_vat: Extracted[Amount] | None = _bt("BT-110", "Invoice total VAT amount")
    total_with_vat: Extracted[Amount] | None = _bt("BT-112", "Invoice total amount with VAT")
    prepaid: Extracted[Amount] | None = _bt("BT-113", "Paid amount")
    rounding: Extracted[Amount] | None = _bt("BT-114", "Rounding amount")
    amount_due: Extracted[Amount] | None = _bt("BT-115", "Amount due for payment")


class Invoice(_Model):
    """Canonical invoice (EN 16931 subset) as produced by any extractor."""

    document_id: str = Field(min_length=1, description="Internal id of the received document.")
    source_format: SourceFormat

    invoice_number: Extracted[str] | None = _bt("BT-1", "Invoice number")
    issue_date: Extracted[date] | None = _bt("BT-2", "Invoice issue date")
    type_code: Extracted[InvoiceTypeCode] | None = _bt("BT-3", "Invoice type code")
    currency: Extracted[CurrencyCode] | None = _bt("BT-5", "Invoice currency code")
    due_date: Extracted[date] | None = _bt("BT-9", "Payment due date")
    buyer_reference: Extracted[str] | None = _bt("BT-10", "Buyer reference (Leitweg-ID for XRechnung)")
    order_reference: Extracted[str] | None = _bt("BT-13", "Purchase order reference")
    despatch_advice_reference: Extracted[str] | None = _bt(
        "BT-16", "Despatch advice (delivery note) reference"
    )
    preceding_invoice_reference: Extracted[str] | None = _bt("BT-25", "Preceding invoice reference")
    delivery_date: Extracted[date] | None = _bt("BT-72", "Actual delivery date")
    notes: tuple[Extracted[str], ...] = Field(default=(), description="BT-22 Invoice note")

    seller: Party = Field(default_factory=Party)
    buyer: Party = Field(default_factory=Party)
    payment: PaymentInstructions = Field(default_factory=PaymentInstructions)
    lines: tuple[InvoiceLine, ...] = ()
    vat_breakdown: tuple[VatBreakdown, ...] = ()
    totals: DocumentTotals = Field(default_factory=DocumentTotals)


def _paths(model: type[BaseModel], prefix: str = "") -> list[str]:
    paths: list[str] = []
    nested: dict[str, tuple[type[BaseModel], str]] = {
        "seller": (Party, ""),
        "buyer": (Party, ""),
        "address": (PostalAddress, ""),
        "payment": (PaymentInstructions, ""),
        "totals": (DocumentTotals, ""),
        "lines": (InvoiceLine, "[]"),
        "vat_breakdown": (VatBreakdown, "[]"),
    }
    for name in model.model_fields:
        if name in {"document_id", "source_format"}:
            continue
        if name in nested:
            sub, suffix = nested[name]
            paths.extend(_paths(sub, f"{prefix}{name}{suffix}."))
        else:
            paths.append(f"{prefix}{name}")
    return paths


INVOICE_FIELD_PATHS: frozenset[str] = frozenset(_paths(Invoice))
"""Dotted paths of every extractable invoice field, e.g. ``buyer_reference``,
``seller.vat_id``, ``lines[].batch_number``. Tenant ``mandatory_fields`` must
use these paths."""
