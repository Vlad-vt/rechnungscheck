"""Tenant master data: suppliers, products, unit conversions, price agreements.

Master data is tenant-scoped by storage (directory, Postgres row-level
security), never by a field the caller can set.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from rechnungscheck.domain.types import Amount, CountryCode, Percent, Quantity, UnitCode


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Address(_Model):
    street: str
    post_code: str
    city: str
    country_code: CountryCode


class Supplier(_Model):
    supplier_id: str = Field(pattern=r"^SUP-[0-9]{4}$")
    name: str
    vat_id: str
    address: Address
    iban: str
    bic: str
    contact_name: str
    contact_phone: str
    contact_email: str
    electronic_address: str = Field(
        description="BT-34 seller electronic address (here: an email, scheme EM)."
    )
    language: str = Field(pattern=r"^(de|en)$", description="Language for supplier correspondence.")
    payment_terms_days: int = Field(ge=0, le=120)


class Product(_Model):
    product_id: str = Field(pattern=r"^ART-[0-9]{5}$", description="Buyer's item id (BT-156).")
    gtin: str = Field(pattern=r"^[0-9]{13}$")
    name: str
    category: str
    unit_code: UnitCode = Field(description="Unit the product is ordered and priced in.")
    vat_rate: Percent
    batch_tracked: bool = False
    serial_tracked: bool = False
    shelf_life_days: int | None = Field(default=None, ge=1, description="Typical shelf life from production.")


class UnitConversion(_Model):
    """``quantity_in_to_unit = quantity_in_from_unit * factor`` for one product."""

    product_id: str
    from_unit: UnitCode
    to_unit: UnitCode
    factor: Decimal = Field(gt=0)


class PriceAgreement(_Model):
    agreement_id: str = Field(pattern=r"^PA-[0-9]{5}$")
    supplier_id: str
    product_id: str
    supplier_item_id: str = Field(description="Supplier's item id (BT-155).")
    unit_code: UnitCode
    net_price: Amount
    price_base_quantity: Quantity = Decimal(1)
    valid_from: date
    valid_to: date | None = None


class TenantMasterData(_Model):
    suppliers: tuple[Supplier, ...]
    products: tuple[Product, ...]
    unit_conversions: tuple[UnitConversion, ...]
    price_agreements: tuple[PriceAgreement, ...]
