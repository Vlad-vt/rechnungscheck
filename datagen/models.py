"""Dataset case model: one purchase order, delivery note and invoice triple with labels."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from rechnungscheck.domain.invoice import Invoice, SourceFormat
from rechnungscheck.domain.orders import DeliveryNote, PurchaseOrder
from rechnungscheck.tenancy import Action


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DiscrepancyType(StrEnum):
    SHORT_DELIVERY = "short_delivery"
    OVER_DELIVERY = "over_delivery"
    PRICE_DEVIATION = "price_deviation"
    WRONG_VAT_RATE = "wrong_vat_rate"
    MISSING_LINE = "missing_line"
    EXTRA_LINE = "extra_line"
    DUPLICATE_INVOICE = "duplicate_invoice"
    ARITHMETIC_ERROR = "arithmetic_error"
    MISSING_MANDATORY_FIELD = "missing_mandatory_field"
    EXPIRED_BATCH = "expired_batch"
    SHORT_SHELF_LIFE = "short_shelf_life"
    CHANGED_IBAN = "changed_iban"
    UNIT_MISMATCH = "unit_mismatch"
    ROUNDING = "rounding"
    NO_GOODS_RECEIPT = "no_goods_receipt"


class Injection(StrEnum):
    NONE = "none"
    VISIBLE = "visible"
    HIDDEN = "hidden"


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"


class DiscrepancyLabel(_Model):
    type: DiscrepancyType
    line_no: int | None = Field(default=None, description="Invoice line (1-based); None = document level.")
    field: str | None = Field(default=None, description="INVOICE_FIELD_PATHS entry, for field-level issues.")
    within_tolerance: bool = False
    impact_net_eur: Decimal = Field(
        default=Decimal(0), description="Invoiced minus payable net amount; positive = buyer overcharged."
    )
    impact_gross_eur: Decimal = Decimal(0)
    detail: str = ""


class ExpectedOutcome(_Model):
    """Oracle answer, derived from the labels and the tenant config by ``datagen.labels``.

    Independent of ``rechnungscheck.policy`` on purpose: the product is evaluated
    against this oracle, not against itself."""

    requires_human: bool
    action: Action
    reasons: tuple[str, ...]


class InvoiceHistoryEntry(_Model):
    supplier_id: str
    invoice_number: str
    issue_date: str
    total_with_vat: Decimal
    status: str = "paid"


class Case(_Model):
    case_id: str
    tenant_id: str
    split: Split
    scenario: str
    source_format: SourceFormat
    injection: Injection = Injection.NONE
    injection_text: str | None = None
    purchase_order: PurchaseOrder
    delivery_note: DeliveryNote | None = None
    invoice: Invoice = Field(description="Ground truth: what is printed or encoded in the invoice document.")
    labels: tuple[DiscrepancyLabel, ...]
    expected: ExpectedOutcome
    files: dict[str, str] = Field(
        default_factory=dict, description="role -> path relative to the dataset root"
    )
