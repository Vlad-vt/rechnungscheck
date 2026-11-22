"""Purchase orders and delivery notes (goods receipts) the invoice is matched against."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from rechnungscheck.domain.types import Amount, Quantity, UnitCode


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PurchaseOrderLine(_Model):
    line_no: int = Field(ge=1)
    product_id: str
    gtin: str
    description: str
    quantity: Quantity
    unit_code: UnitCode
    net_price: Amount
    price_base_quantity: Quantity


class PurchaseOrder(_Model):
    po_number: str
    supplier_id: str
    order_date: date
    buyer_reference: str
    lines: tuple[PurchaseOrderLine, ...] = Field(min_length=1)


class DeliveryNoteLine(_Model):
    line_no: int = Field(ge=1)
    po_line_no: int = Field(ge=1)
    product_id: str
    gtin: str
    description: str
    quantity: Quantity
    unit_code: UnitCode
    batch_number: str | None = None
    best_before_date: date | None = None
    serial_numbers: tuple[str, ...] = ()


class DeliveryNote(_Model):
    dn_number: str
    po_number: str
    supplier_id: str
    delivery_date: date
    lines: tuple[DeliveryNoteLine, ...] = Field(min_length=1)
