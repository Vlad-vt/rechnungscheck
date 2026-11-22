"""Render a ground-truth invoice as OASIS UBL 2.1 (XRechnung 3.0 CIUS)."""

from __future__ import annotations

from lxml import etree

from datagen.render.common import PEPPOL_PROCESS, XRECHNUNG_ID, amount, dec, line_note, number, price, txt, v
from rechnungscheck.domain.invoice import Invoice, Party

NS = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


def _q(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def _sub(parent: etree._Element, tag: str, text: str | None = None, **attrs: str) -> etree._Element:
    el = etree.SubElement(parent, _q(tag), attrs)
    if text is not None:
        el.text = text
    return el


def _vat(parent: etree._Element, tag: str, category: str, rate: str) -> None:
    tc = _sub(parent, tag)
    _sub(tc, "cbc:ID", category)
    _sub(tc, "cbc:Percent", rate)
    _sub(_sub(tc, "cac:TaxScheme"), "cbc:ID", "VAT")


def _party(parent: etree._Element, tag: str, p: Party, seller: bool) -> None:
    party = _sub(_sub(parent, tag), "cac:Party")
    if p.electronic_address:
        _sub(party, "cbc:EndpointID", p.electronic_address.value, schemeID="EM")
    if p.address:
        a = _sub(party, "cac:PostalAddress")
        if p.address.street:
            _sub(a, "cbc:StreetName", p.address.street.value)
        if p.address.city:
            _sub(a, "cbc:CityName", p.address.city.value)
        if p.address.post_code:
            _sub(a, "cbc:PostalZone", p.address.post_code.value)
        if p.address.country_code:
            _sub(_sub(a, "cac:Country"), "cbc:IdentificationCode", p.address.country_code.value)
    if p.vat_id:
        pts = _sub(party, "cac:PartyTaxScheme")
        _sub(pts, "cbc:CompanyID", p.vat_id.value)
        _sub(_sub(pts, "cac:TaxScheme"), "cbc:ID", "VAT")
    if p.name:
        _sub(_sub(party, "cac:PartyLegalEntity"), "cbc:RegistrationName", p.name.value)
    if seller and (p.contact_name or p.contact_phone or p.contact_email):
        c = _sub(party, "cac:Contact")
        if p.contact_name:
            _sub(c, "cbc:Name", p.contact_name.value)
        if p.contact_phone:
            _sub(c, "cbc:Telephone", p.contact_phone.value)
        if p.contact_email:
            _sub(c, "cbc:ElectronicMail", p.contact_email.value)


def render_ubl(inv: Invoice, lang: str) -> bytes:
    cur = v(inv.currency) or "EUR"
    root = etree.Element(f"{{{NS[None]}}}Invoice", nsmap=NS)  # type: ignore[arg-type]  # default ns key None
    _sub(root, "cbc:CustomizationID", XRECHNUNG_ID)
    _sub(root, "cbc:ProfileID", PEPPOL_PROCESS)
    _sub(root, "cbc:ID", txt(inv.invoice_number))
    if inv.issue_date:
        _sub(root, "cbc:IssueDate", inv.issue_date.value.isoformat())
    if inv.due_date:
        _sub(root, "cbc:DueDate", inv.due_date.value.isoformat())
    _sub(root, "cbc:InvoiceTypeCode", str(v(inv.type_code) or "380"))
    for note in inv.notes:
        _sub(root, "cbc:Note", note.value)
    _sub(root, "cbc:DocumentCurrencyCode", cur)
    if inv.buyer_reference:
        _sub(root, "cbc:BuyerReference", inv.buyer_reference.value)
    if inv.order_reference:
        _sub(_sub(root, "cac:OrderReference"), "cbc:ID", inv.order_reference.value)
    if inv.despatch_advice_reference:
        _sub(_sub(root, "cac:DespatchDocumentReference"), "cbc:ID", inv.despatch_advice_reference.value)
    _party(root, "cac:AccountingSupplierParty", inv.seller, seller=True)
    _party(root, "cac:AccountingCustomerParty", inv.buyer, seller=False)
    if inv.delivery_date:
        _sub(_sub(root, "cac:Delivery"), "cbc:ActualDeliveryDate", inv.delivery_date.value.isoformat())
    pm = _sub(root, "cac:PaymentMeans")
    _sub(pm, "cbc:PaymentMeansCode", v(inv.payment.means_code) or "58")
    if inv.payment.iban:
        acc = _sub(pm, "cac:PayeeFinancialAccount")
        _sub(acc, "cbc:ID", inv.payment.iban.value)
        if inv.payment.bic:
            _sub(_sub(acc, "cac:FinancialInstitutionBranch"), "cbc:ID", inv.payment.bic.value)
    if inv.payment.terms:
        _sub(_sub(root, "cac:PaymentTerms"), "cbc:Note", inv.payment.terms.value)

    tt = _sub(root, "cac:TaxTotal")
    _sub(tt, "cbc:TaxAmount", amount(dec(inv.totals.total_vat)), currencyID=cur)
    for vb in inv.vat_breakdown:
        sub = _sub(tt, "cac:TaxSubtotal")
        _sub(sub, "cbc:TaxableAmount", amount(dec(vb.taxable_amount)), currencyID=cur)
        _sub(sub, "cbc:TaxAmount", amount(dec(vb.tax_amount)), currencyID=cur)
        _vat(sub, "cac:TaxCategory", str(v(vb.category) or "S"), number(dec(vb.rate)))

    tot = inv.totals
    lmt = _sub(root, "cac:LegalMonetaryTotal")
    _sub(lmt, "cbc:LineExtensionAmount", amount(dec(tot.sum_of_line_net)), currencyID=cur)
    _sub(lmt, "cbc:TaxExclusiveAmount", amount(dec(tot.total_without_vat)), currencyID=cur)
    _sub(lmt, "cbc:TaxInclusiveAmount", amount(dec(tot.total_with_vat)), currencyID=cur)
    _sub(lmt, "cbc:PayableAmount", amount(dec(tot.amount_due)), currencyID=cur)

    for line in inv.lines:
        il = _sub(root, "cac:InvoiceLine")
        _sub(il, "cbc:ID", txt(line.line_id))
        lnote = line_note(line, lang)
        if lnote:
            _sub(il, "cbc:Note", lnote)
        unit = v(line.unit_code) or "C62"
        _sub(il, "cbc:InvoicedQuantity", number(dec(line.quantity)), unitCode=unit)
        _sub(il, "cbc:LineExtensionAmount", amount(dec(line.line_net_amount)), currencyID=cur)
        if line.order_line_reference:
            _sub(_sub(il, "cac:OrderLineReference"), "cbc:LineID", line.order_line_reference.value)
        item = _sub(il, "cac:Item")
        _sub(item, "cbc:Name", txt(line.item_name))
        if line.buyer_item_id:
            _sub(_sub(item, "cac:BuyersItemIdentification"), "cbc:ID", line.buyer_item_id.value)
        if line.seller_item_id:
            _sub(_sub(item, "cac:SellersItemIdentification"), "cbc:ID", line.seller_item_id.value)
        if line.gtin:
            _sub(_sub(item, "cac:StandardItemIdentification"), "cbc:ID", line.gtin.value, schemeID="0160")
        _vat(item, "cac:ClassifiedTaxCategory", str(v(line.vat_category) or "S"), number(dec(line.vat_rate)))
        pr = _sub(il, "cac:Price")
        _sub(pr, "cbc:PriceAmount", price(dec(line.net_price)), currencyID=cur)
        if line.price_base_quantity and line.price_base_quantity.value != 1:
            _sub(pr, "cbc:BaseQuantity", number(line.price_base_quantity.value), unitCode=unit)
    return bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True))
