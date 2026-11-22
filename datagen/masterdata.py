"""Generate tenant master data from the curated catalogue."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

from datagen import catalog, ids
from datagen.rng import stream
from rechnungscheck.domain.masterdata import (
    Address,
    PriceAgreement,
    Product,
    Supplier,
    TenantMasterData,
    UnitConversion,
)

AGREEMENTS_VALID_FROM = date(2026, 1, 1)


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def _domain(supplier_name: str) -> str:
    base = _slug(supplier_name.replace(" GmbH", "").replace(" KG", "").replace(" eG", ""))
    return f"{base}.example"


def build_master_data(tenant_id: str, seed: int) -> TenantMasterData:
    rng = stream(seed, "masterdata", tenant_id)
    suppliers: list[Supplier] = []
    for i, s in enumerate(catalog.SUPPLIERS[tenant_id]):
        dom = _domain(s.name)
        local = _slug(s.contact).split("-")[0]
        suppliers.append(
            Supplier(
                supplier_id=f"SUP-{i + 1:04d}",
                name=s.name,
                vat_id=ids.make_de_vat_id(rng),
                address=Address(street=s.street, post_code=s.post_code, city=s.city, country_code="DE"),
                iban=ids.make_de_iban(rng),
                bic=ids.make_bic(rng),
                contact_name=s.contact,
                contact_phone=f"+49 {rng.randint(100, 999)} {rng.randint(100000, 9999999)}",
                contact_email=f"{local}@{dom}",
                electronic_address=f"rechnung@{dom}",
                language=s.language,
                payment_terms_days=s.payment_terms_days,
            )
        )

    products: list[Product] = []
    conversions: list[UnitConversion] = []
    agreements: list[PriceAgreement] = []
    for j, p in enumerate(catalog.PRODUCTS[tenant_id]):
        product_id = f"ART-{(j + 1) * 7 + 10000:05d}"
        products.append(
            Product(
                product_id=product_id,
                gtin=ids.make_gtin(rng),
                name=p.name,
                category=p.category,
                unit_code=p.unit,
                vat_rate=p.vat,
                batch_tracked=p.batch,
                serial_tracked=p.serial,
                shelf_life_days=p.shelf_life_days,
            )
        )
        if p.unit == "XCT" and p.pack_size:
            conversions.append(
                UnitConversion(
                    product_id=product_id, from_unit="XCT", to_unit="C62", factor=Decimal(p.pack_size)
                )
            )
        # Each tenant negotiates its own price: +/- 8 % around the list price.
        factor = Decimal(rng.randint(92, 108)) / Decimal(100)
        price = (p.price * factor).quantize(Decimal("0.01"))
        supplier_id = suppliers[p.supplier].supplier_id
        agreements.append(
            PriceAgreement(
                agreement_id=f"PA-{j + 1:05d}",
                supplier_id=supplier_id,
                product_id=product_id,
                supplier_item_id=f"{supplier_id[-2:]}-{rng.randint(100000, 999999)}",
                unit_code=p.unit,
                net_price=price,
                valid_from=AGREEMENTS_VALID_FROM,
            )
        )
    # The shared supplier also sells two products in every tenant (if not already assigned).
    shared_idx = next(i for i, s in enumerate(catalog.SUPPLIERS[tenant_id]) if s == catalog.SHARED_SUPPLIER)
    shared_id = suppliers[shared_idx].supplier_id
    assigned = {a.product_id for a in agreements if a.supplier_id == shared_id}
    for k, prod in enumerate(products[:2]):
        if prod.product_id in assigned:
            continue
        base = next(a for a in agreements if a.product_id == prod.product_id)
        agreements.append(
            PriceAgreement(
                agreement_id=f"PA-{len(agreements) + 1:05d}",
                supplier_id=shared_id,
                product_id=prod.product_id,
                supplier_item_id=f"KH-{rng.randint(100000, 999999)}",
                unit_code=prod.unit_code,
                net_price=(base.net_price * Decimal("1.03")).quantize(Decimal("0.01")),
                valid_from=AGREEMENTS_VALID_FROM,
            )
        )
        _ = k
    return TenantMasterData(
        suppliers=tuple(suppliers),
        products=tuple(products),
        unit_conversions=tuple(conversions),
        price_agreements=tuple(agreements),
    )
