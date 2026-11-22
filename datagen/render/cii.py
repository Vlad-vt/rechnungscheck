"""Render a ground-truth invoice as UN/CEFACT CII (XRechnung 3.0 or Factur-X EN 16931)."""

from __future__ import annotations

from datetime import date

from lxml import etree

from datagen.render.common import (
    EN16931_ID,
    PEPPOL_PROCESS,
    XRECHNUNG_ID,
    amount,
    dec,
    line_note,
    number,
    price,
    txt,
    v,
    ymd,
)
from rechnungscheck.domain.invoice import Invoice, Party

NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
}


def _q(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def _sub(parent: etree._Element, tag: str, text: str | None = None, **attrs: str) -> etree._Element:
    el = etree.SubElement(parent, _q(tag), attrs)
    if text is not None:
        el.text = text
    return el


def _date(parent: etree._Element, tag: str, d: date | None) -> None:
    if d is None:
        return
    wrapper = _sub(parent, tag)
    _sub(wrapper, "udt:DateTimeString", ymd(d), format="102")


def _party(parent: etree._Element, tag: str, p: Party, seller: bool) -> None:
    tp = _sub(parent, tag)
    if p.name:
        _sub(tp, "ram:Name", p.name.value)
    if seller and (p.contact_name or p.contact_phone or p.contact_email):
        c = _sub(tp, "ram:DefinedTradeContact")
        if p.contact_name:
            _sub(c, "ram:PersonName", p.contact_name.value)
        if p.contact_phone:
            _sub(_sub(c, "ram:TelephoneUniversalCommunication"), "ram:CompleteNumber", p.contact_phone.value)
        if p.contact_email:
            _sub(_sub(c, "ram:EmailURIUniversalCommunication"), "ram:URIID", p.contact_email.value)
    if p.address:
        a = _sub(tp, "ram:PostalTradeAddress")
        if p.address.post_code:
            _sub(a, "ram:PostcodeCode", p.address.post_code.value)
        if p.address.street:
            _sub(a, "ram:LineOne", p.address.street.value)
        if p.address.city:
            _sub(a, "ram:CityName", p.address.city.value)
        if p.address.country_code:
            _sub(a, "ram:CountryID", p.address.country_code.value)
    if p.electronic_address:
        _sub(
            _sub(tp, "ram:URIUniversalCommunication"), "ram:URIID", p.electronic_address.value, schemeID="EM"
        )
    if p.vat_id:
        _sub(_sub(tp, "ram:SpecifiedTaxRegistration"), "ram:ID", p.vat_id.value, schemeID="VA")


def render_cii(inv: Invoice, lang: str, profile: str = "xrechnung") -> bytes:
    """``profile``: ``xrechnung`` (XRechnung 3.0 CIUS) or ``en16931`` (Factur-X EN 16931 for ZUGFeRD)."""
    root = etree.Element(_q("rsm:CrossIndustryInvoice"), nsmap=NS)
    ctx = _sub(root, "rsm:ExchangedDocumentContext")
    if profile == "xrechnung":
        _sub(_sub(ctx, "ram:BusinessProcessSpecifiedDocumentContextParameter"), "ram:ID", PEPPOL_PROCESS)
    guideline = XRECHNUNG_ID if profile == "xrechnung" else EN16931_ID
    _sub(_sub(ctx, "ram:GuidelineSpecifiedDocumentContextParameter"), "ram:ID", guideline)

    doc = _sub(root, "rsm:ExchangedDocument")
    _sub(doc, "ram:ID", txt(inv.invoice_number))
    _sub(doc, "ram:TypeCode", (v(inv.type_code) or "380").__str__())
    _date(doc, "ram:IssueDateTime", inv.issue_date.value if inv.issue_date else None)
    for note in inv.notes:
        _sub(_sub(doc, "ram:IncludedNote"), "ram:Content", note.value)

    tx = _sub(root, "rsm:SupplyChainTradeTransaction")
    for line in inv.lines:
        li = _sub(tx, "ram:IncludedSupplyChainTradeLineItem")
        ad = _sub(li, "ram:AssociatedDocumentLineDocument")
        _sub(ad, "ram:LineID", txt(line.line_id))
        lnote = line_note(line, lang)
        if lnote:
            _sub(_sub(ad, "ram:IncludedNote"), "ram:Content", lnote)
        prod = _sub(li, "ram:SpecifiedTradeProduct")
        if line.gtin:
            _sub(prod, "ram:GlobalID", line.gtin.value, schemeID="0160")
        if line.seller_item_id:
            _sub(prod, "ram:SellerAssignedID", line.seller_item_id.value)
        if line.buyer_item_id:
            _sub(prod, "ram:BuyerAssignedID", line.buyer_item_id.value)
        _sub(prod, "ram:Name", txt(line.item_name))
        agr = _sub(li, "ram:SpecifiedLineTradeAgreement")
        if line.order_line_reference:
            _sub(_sub(agr, "ram:BuyerOrderReferencedDocument"), "ram:LineID", line.order_line_reference.value)
        unit = v(line.unit_code) or "C62"
        net = _sub(agr, "ram:NetPriceProductTradePrice")
        _sub(net, "ram:ChargeAmount", price(dec(line.net_price)))
        if line.price_base_quantity and line.price_base_quantity.value != 1:
            _sub(net, "ram:BasisQuantity", number(line.price_base_quantity.value), unitCode=unit)
        dlv = _sub(li, "ram:SpecifiedLineTradeDelivery")
        _sub(dlv, "ram:BilledQuantity", number(dec(line.quantity)), unitCode=unit)
        st = _sub(li, "ram:SpecifiedLineTradeSettlement")
        tax = _sub(st, "ram:ApplicableTradeTax")
        _sub(tax, "ram:TypeCode", "VAT")
        _sub(tax, "ram:CategoryCode", str(v(line.vat_category) or "S"))
        _sub(tax, "ram:RateApplicablePercent", number(dec(line.vat_rate)))
        _sub(
            _sub(st, "ram:SpecifiedTradeSettlementLineMonetarySummation"),
            "ram:LineTotalAmount",
            amount(dec(line.line_net_amount)),
        )

    agr = _sub(tx, "ram:ApplicableHeaderTradeAgreement")
    if inv.buyer_reference:
        _sub(agr, "ram:BuyerReference", inv.buyer_reference.value)
    _party(agr, "ram:SellerTradeParty", inv.seller, seller=True)
    _party(agr, "ram:BuyerTradeParty", inv.buyer, seller=False)
    if inv.order_reference:
        _sub(_sub(agr, "ram:BuyerOrderReferencedDocument"), "ram:IssuerAssignedID", inv.order_reference.value)

    dlv = _sub(tx, "ram:ApplicableHeaderTradeDelivery")
    if inv.delivery_date:
        ev = _sub(dlv, "ram:ActualDeliverySupplyChainEvent")
        _date(ev, "ram:OccurrenceDateTime", inv.delivery_date.value)
    if inv.despatch_advice_reference:
        _sub(
            _sub(dlv, "ram:DespatchAdviceReferencedDocument"),
            "ram:IssuerAssignedID",
            inv.despatch_advice_reference.value,
        )

    st = _sub(tx, "ram:ApplicableHeaderTradeSettlement")
    _sub(st, "ram:InvoiceCurrencyCode", v(inv.currency) or "EUR")
    pm = _sub(st, "ram:SpecifiedTradeSettlementPaymentMeans")
    _sub(pm, "ram:TypeCode", v(inv.payment.means_code) or "58")
    if inv.payment.iban:
        _sub(_sub(pm, "ram:PayeePartyCreditorFinancialAccount"), "ram:IBANID", inv.payment.iban.value)
    if inv.payment.bic:
        _sub(_sub(pm, "ram:PayeeSpecifiedCreditorFinancialInstitution"), "ram:BICID", inv.payment.bic.value)
    for vb in inv.vat_breakdown:
        t = _sub(st, "ram:ApplicableTradeTax")
        _sub(t, "ram:CalculatedAmount", amount(dec(vb.tax_amount)))
        _sub(t, "ram:TypeCode", "VAT")
        _sub(t, "ram:BasisAmount", amount(dec(vb.taxable_amount)))
        _sub(t, "ram:CategoryCode", str(v(vb.category) or "S"))
        _sub(t, "ram:RateApplicablePercent", number(dec(vb.rate)))
    terms = _sub(st, "ram:SpecifiedTradePaymentTerms")
    if inv.payment.terms:
        _sub(terms, "ram:Description", inv.payment.terms.value)
    if inv.due_date:
        _date(terms, "ram:DueDateDateTime", inv.due_date.value)
    tot = inv.totals
    ms = _sub(st, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
    _sub(ms, "ram:LineTotalAmount", amount(dec(tot.sum_of_line_net)))
    _sub(ms, "ram:TaxBasisTotalAmount", amount(dec(tot.total_without_vat)))
    _sub(ms, "ram:TaxTotalAmount", amount(dec(tot.total_vat)), currencyID=v(inv.currency) or "EUR")
    _sub(ms, "ram:GrandTotalAmount", amount(dec(tot.total_with_vat)))
    _sub(ms, "ram:DuePayableAmount", amount(dec(tot.amount_due)))
    return bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True))
