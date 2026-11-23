"""Synthetic supplier framework contracts (Rahmenverträge) for the knowledge base.

Written in the supplier's correspondence language. The clauses the
Investigator needs (payment terms, tolerances, short delivery, price changes,
credit notes, shelf life, serial numbers, bank-detail changes) are present in
every contract, but values differ per tenant and supplier. The shared supplier
gets near-identical contracts in all tenants with different numbers, so a
cross-tenant retrieval leak produces a detectably wrong answer.
"""

from __future__ import annotations

from datagen.catalog import TenantSeed
from rechnungscheck.domain.masterdata import Supplier, TenantMasterData
from rechnungscheck.tenancy import TenantConfig

_DE = """# Rahmenliefervertrag {contract_id}

**Käufer:** {buyer}
**Lieferant:** {supplier} ({supplier_id}), {city}
**Gültig ab:** 01.01.2026, unbefristet, Kündigung mit 3 Monaten Frist zum Quartalsende.

## § 1 Preise
Es gelten die vereinbarten Nettopreise der Preisvereinbarungen des Käufers.
Preisänderungen bedürfen einer schriftlichen Ankündigung mit mindestens {notice_days} Tagen Vorlauf.
Nicht angekündigte Preiserhöhungen werden nicht anerkannt; der Käufer zahlt den vereinbarten Preis.

## § 2 Mengen und Mindermengen
{quantity_clause}
Bei Minderlieferung wird nur die tatsächlich gelieferte Menge vergütet. Der Lieferant stellt für
zu viel berechnete Mengen unaufgefordert eine Gutschrift aus.

## § 3 Rechnungsstellung
Rechnungen sind als strukturierte E-Rechnung (XRechnung oder ZUGFeRD ab Profil EN 16931) an
{inbox} zu senden. Jede Rechnung muss Bestellnummer und Lieferscheinnummer enthalten.
{mandatory_clause}

## § 4 Zahlung
Zahlungsziel {payment_days} Tage netto ab Rechnungseingang. Skonto wird nicht gewährt.
Änderungen der Bankverbindung werden nur nach schriftlicher Bestätigung durch die Geschäftsführung
des Lieferanten und telefonischer Rückbestätigung durch den Käufer wirksam.

## § 5 Gutschriften
Gutschriften sind innerhalb von {credit_days} Tagen nach Anforderung auszustellen und müssen die
ursprüngliche Rechnungsnummer referenzieren.

## § 6 Haltbarkeit und Rückverfolgbarkeit
{shelf_clause}

## § 7 Sonstiges
Mündliche Nebenabreden bestehen nicht. Gerichtsstand ist der Sitz des Käufers.
"""

_EN = """# Framework supply agreement {contract_id}

**Buyer:** {buyer}
**Supplier:** {supplier} ({supplier_id}), {city}
**Effective:** 1 January 2026, open-ended, three months' notice to the end of a quarter.

## 1 Prices
The net prices in the buyer's price agreements apply. Price changes require written notice at
least {notice_days} days in advance. Unannounced price increases are not accepted; the buyer pays
the agreed price.

## 2 Quantities and short deliveries
{quantity_clause}
For short deliveries only the quantity actually delivered is paid. The supplier issues a credit
note for over-invoiced quantities without being asked.

## 3 Invoicing
Invoices must be sent as structured e-invoices (XRechnung or ZUGFeRD, profile EN 16931 or higher)
to {inbox}. Every invoice must state the purchase order number and the delivery note number.
{mandatory_clause}

## 4 Payment
Payment term {payment_days} days net from receipt of invoice. No early-payment discount.
Changes of bank details only take effect after written confirmation by the supplier's management
and a call-back confirmation by the buyer.

## 5 Credit notes
Credit notes must be issued within {credit_days} days of request and must reference the original
invoice number.

## 6 Shelf life and traceability
{shelf_clause}

## 7 Miscellaneous
There are no oral side agreements. Place of jurisdiction is the buyer's registered office.
"""


def _clauses(cfg: TenantConfig, lang: str) -> dict[str, str]:
    de = lang == "de"
    kgm = cfg.tolerances.quantity_by_unit.get("KGM")
    if kgm is not None and kgm.relative > 0:
        pct = f"{kgm.relative * 100:.0f}"
        quantity = (
            f"Bei Gewichtsware (kg) gilt eine Mengentoleranz von ±{pct} %. Sonst gilt keine Toleranz."
            if de
            else f"For goods sold by weight (kg) a quantity tolerance of ±{pct} % applies. Otherwise none."
        )
    else:
        quantity = (
            "Es gilt keine Mengen- oder Preistoleranz; jede Abweichung ist zu klären."
            if de
            else "No quantity or price tolerance applies; every deviation must be clarified."
        )
    if "lines[].serial_numbers" in cfg.mandatory_fields:
        mandatory = (
            "Für serialisierte Ware sind die Seriennummern je Position auf Lieferschein und Rechnung anzugeben."
            if de
            else "For serialised goods the serial numbers per line must be stated on delivery note and invoice."
        )
    elif "lines[].batch_number" in cfg.mandatory_fields:
        mandatory = (
            "Je Position sind Chargennummer und Mindesthaltbarkeitsdatum anzugeben."
            if de
            else "Batch number and best-before date must be stated per line."
        )
    else:
        mandatory = ""
    if cfg.shelf_life is not None and cfg.shelf_life.min_remaining_days > 0:
        days = cfg.shelf_life.min_remaining_days
        shelf = (
            f"Ware muss bei Anlieferung eine Restlaufzeit von mindestens {days} Tagen haben. Ware mit kürzerer "
            "Restlaufzeit wird nicht angenommen bzw. per Gutschrift zurückbelastet."
            if de
            else f"Goods must have at least {days} days of remaining shelf life on delivery. Goods with a shorter "
            "remaining shelf life are rejected or charged back by credit note."
        )
    elif cfg.shelf_life is not None:
        shelf = (
            "Abgelaufene Ware wird nicht vergütet und per Gutschrift zurückbelastet."
            if de
            else "Expired goods are not paid and are charged back by credit note."
        )
    else:
        shelf = (
            "Seriennummern sind vollständig und eindeutig zu melden; fehlende Seriennummern führen zur Klärung."
            if de
            else "Serial numbers must be complete and unique; missing serial numbers lead to clarification."
        )
    return {"quantity_clause": quantity, "mandatory_clause": mandatory, "shelf_clause": shelf}


def render_contract(
    cfg: TenantConfig, tseed: TenantSeed, supplier: Supplier, index: int, shared: bool
) -> tuple[str, str]:
    """Return ``(filename, markdown)`` for one supplier contract."""
    lang = supplier.language
    template = _DE if lang == "de" else _EN
    # Tenant-specific numbers, also for the shared supplier.
    notice = tseed.contract_terms.price_change_notice_days
    credit = tseed.contract_terms.credit_note_days
    if shared:
        notice += 15
    text = template.format(
        contract_id=f"RV-{cfg.tenant_id[:3].upper()}-{index + 1:03d}",
        buyer=tseed.buyer.name,
        supplier=supplier.name,
        supplier_id=supplier.supplier_id,
        city=supplier.address.city,
        notice_days=notice,
        inbox=f"rechnungseingang@{cfg.tenant_id}.example",
        payment_days=supplier.payment_terms_days,
        credit_days=credit,
        **_clauses(cfg, lang),
    )
    return f"{supplier.supplier_id.lower()}-rahmenvertrag.md", text


def render_contracts(cfg: TenantConfig, tseed: TenantSeed, md: TenantMasterData) -> dict[str, str]:
    return dict(
        render_contract(cfg, tseed, s, i, shared=i == tseed.shared_index) for i, s in enumerate(md.suppliers)
    )
