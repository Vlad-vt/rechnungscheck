"""Per-tenant generator seed, read from ``tenants/<tenant_id>/datagen.yaml``.

Demo tenants only: a real tenant brings its own master data. Keeping the seed in
the tenant directory means a new demo tenant needs no code change.

One supplier per tenant is marked ``shared: true``. It supplies every tenant
under the same name but with DIFFERENT bank details, prices and contract
terms, so that cross-tenant leakage produces a detectably wrong answer.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SEED_FILE = "datagen.yaml"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BuyerSeed(_Model):
    name: str
    street: str
    post_code: str
    city: str


class SupplierSeed(_Model):
    name: str
    street: str
    post_code: str
    city: str
    contact: str
    language: Literal["de", "en"] = "de"
    payment_terms_days: int = Field(default=30, ge=0, le=120)
    shared: bool = False


class ProductSeed(_Model):
    name: str
    category: str
    unit: Literal["C62", "KGM", "XCT"]
    vat: Decimal
    price: Decimal = Field(gt=0, description="List net price per unit.")
    supplier: int = Field(ge=0, description="Index into the tenant's supplier list.")
    pack_size: int | None = Field(default=None, ge=2, description="Pieces per carton (XCT only).")
    batch: bool = False
    serial: bool = False
    shelf_life_days: int | None = Field(default=None, ge=1)


class ContractTerms(_Model):
    price_change_notice_days: int = Field(ge=0)
    credit_note_days: int = Field(ge=1)


class TenantSeed(_Model):
    buyer: BuyerSeed
    contract_terms: ContractTerms
    suppliers: tuple[SupplierSeed, ...] = Field(min_length=1)
    products: tuple[ProductSeed, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if sum(s.shared for s in self.suppliers) != 1:
            raise ValueError("exactly one supplier must be marked shared: true")
        for p in self.products:
            if p.supplier >= len(self.suppliers):
                raise ValueError(f"product {p.name!r} references supplier index {p.supplier}")
            if (p.unit == "XCT") != (p.pack_size is not None):
                raise ValueError(f"product {p.name!r}: pack_size is required for XCT and only for XCT")
        return self

    @property
    def shared_index(self) -> int:
        return next(i for i, s in enumerate(self.suppliers) if s.shared)


def load_seed(tenant_dir: Path) -> TenantSeed:
    raw = yaml.safe_load((tenant_dir / SEED_FILE).read_text(encoding="utf-8"))
    return TenantSeed.model_validate(raw)
