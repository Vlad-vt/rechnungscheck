"""UN/CEFACT CII (XRechnung CII, Factur-X / ZUGFeRD 2.x) -> canonical invoice."""

from __future__ import annotations

from lxml import etree

from rechnungscheck.domain.invoice import (
    DocumentTotals,
    Invoice,
    InvoiceLine,
    Party,
    PaymentInstructions,
    PostalAddress,
    SourceFormat,
    VatBreakdown,
)
from rechnungscheck.extraction.result import ExtractionResult
from rechnungscheck.extraction.xmlreader import Raw, XmlReader, parse_line_note
from rechnungscheck.extraction.xmlsafe import parse_xml

NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}
ROOT_TAG = f"{{{NS['rsm']}}}CrossIndustryInvoice"


def _clean(d: dict[str, Raw | object | None]) -> dict[str, object]:
    return {k: v for k, v in d.items() if v is not None}


def _party(r: XmlReader, el: etree._Element | None, seller: bool) -> Party:
    if el is None:
        return Party()
    addr = r.first(el, "ram:PostalTradeAddress")
    address = None
    if addr is not None:
        address = r.validated(
            PostalAddress,
            _clean(
                {
                    "street": r.text(addr, "ram:LineOne"),
                    "city": r.text(addr, "ram:CityName"),
                    "post_code": r.text(addr, "ram:PostcodeCode"),
                    "country_code": r.text(addr, "ram:CountryID"),
                }
            ),
        )
    data: dict[str, object] = _clean(
        {
            "name": r.text(el, "ram:Name"),
            "vat_id": r.text(el, "ram:SpecifiedTaxRegistration/ram:ID[@schemeID='VA']"),
            "tax_number": r.text(el, "ram:SpecifiedTaxRegistration/ram:ID[@schemeID='FC']")
            if seller
            else None,
            "electronic_address": r.text(el, "ram:URIUniversalCommunication/ram:URIID"),
            "address": address,
        }
    )
    if seller:
        data |= _clean(
            {
                "contact_name": r.text(el, "ram:DefinedTradeContact/ram:PersonName"),
                "contact_phone": r.text(
                    el, "ram:DefinedTradeContact/ram:TelephoneUniversalCommunication/ram:CompleteNumber"
                ),
                "contact_email": r.text(
                    el, "ram:DefinedTradeContact/ram:EmailURIUniversalCommunication/ram:URIID"
                ),
            }
        )
    return r.validated(Party, data)


def _line(r: XmlReader, li: etree._Element) -> InvoiceLine:
    data: dict[str, object] = _clean(
        {
            "line_id": r.text(li, "ram:AssociatedDocumentLineDocument/ram:LineID"),
            "order_line_reference": r.text(
                li, "ram:SpecifiedLineTradeAgreement/ram:BuyerOrderReferencedDocument/ram:LineID"
            ),
            "item_name": r.text(li, "ram:SpecifiedTradeProduct/ram:Name"),
            "seller_item_id": r.text(li, "ram:SpecifiedTradeProduct/ram:SellerAssignedID"),
            "buyer_item_id": r.text(li, "ram:SpecifiedTradeProduct/ram:BuyerAssignedID"),
            "gtin": r.text(li, "ram:SpecifiedTradeProduct/ram:GlobalID[@schemeID='0160']"),
            "quantity": r.decimal(li, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity"),
            "net_price": r.decimal(
                li, "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount"
            ),
            "price_base_quantity": r.decimal(
                li, "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:BasisQuantity"
            ),
            "line_net_amount": r.decimal(
                li,
                "ram:SpecifiedLineTradeSettlement/ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount",
            ),
            "vat_category": r.text(
                li, "ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:CategoryCode"
            ),
            "vat_rate": r.decimal(
                li, "ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax/ram:RateApplicablePercent"
            ),
        }
    )
    qty_el = r.first(li, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity")
    if qty_el is not None and qty_el.get("unitCode"):
        data["unit_code"] = r.raw(qty_el.get("unitCode"), qty_el)
    data |= parse_line_note(r, r.first(li, "ram:AssociatedDocumentLineDocument/ram:IncludedNote/ram:Content"))
    return r.validated(InvoiceLine, data)


def parse_cii(
    data: bytes,
    document_id: str,
    source_format: SourceFormat = SourceFormat.XRECHNUNG_CII,
    locator_prefix: str = "",
) -> ExtractionResult:
    root = parse_xml(data)
    if root.tag != ROOT_TAG:
        raise ValueError(f"not a CII invoice: root element {root.tag}")
    r = XmlReader(root, NS, evidence_prefix=document_id, locator_prefix=locator_prefix)
    tx = r.first(root, "rsm:SupplyChainTradeTransaction")
    if tx is None:
        raise ValueError("CII invoice without SupplyChainTradeTransaction")
    agr = r.first(tx, "ram:ApplicableHeaderTradeAgreement")
    dlv = r.first(tx, "ram:ApplicableHeaderTradeDelivery")
    st = r.first(tx, "ram:ApplicableHeaderTradeSettlement")
    pm = r.first(st, "ram:SpecifiedTradeSettlementPaymentMeans") if st is not None else None
    ms = r.first(st, "ram:SpecifiedTradeSettlementHeaderMonetarySummation") if st is not None else None
    lines = tuple(_line(r, li) for li in r.all(tx, "ram:IncludedSupplyChainTradeLineItem"))
    breakdown = tuple(
        r.validated(
            VatBreakdown,
            _clean(
                {
                    "category": r.text(t, "ram:CategoryCode"),
                    "rate": r.decimal(t, "ram:RateApplicablePercent"),
                    "taxable_amount": r.decimal(t, "ram:BasisAmount"),
                    "tax_amount": r.decimal(t, "ram:CalculatedAmount"),
                    "exemption_reason": r.text(t, "ram:ExemptionReason"),
                }
            ),
        )
        for t in (r.all(st, "ram:ApplicableTradeTax") if st is not None else [])
    )
    totals = DocumentTotals()
    if ms is not None:
        totals = r.validated(
            DocumentTotals,
            _clean(
                {
                    "sum_of_line_net": r.decimal(ms, "ram:LineTotalAmount"),
                    "allowances": r.decimal(ms, "ram:AllowanceTotalAmount"),
                    "charges": r.decimal(ms, "ram:ChargeTotalAmount"),
                    "total_without_vat": r.decimal(ms, "ram:TaxBasisTotalAmount"),
                    "total_vat": r.decimal(ms, "ram:TaxTotalAmount"),
                    "total_with_vat": r.decimal(ms, "ram:GrandTotalAmount"),
                    "prepaid": r.decimal(ms, "ram:TotalPrepaidAmount"),
                    "rounding": r.decimal(ms, "ram:RoundingAmount"),
                    "amount_due": r.decimal(ms, "ram:DuePayableAmount"),
                }
            ),
        )
    payment = PaymentInstructions()
    if st is not None:
        payment = r.validated(
            PaymentInstructions,
            _clean(
                {
                    "means_code": r.text(pm, "ram:TypeCode") if pm is not None else None,
                    "iban": r.text(pm, "ram:PayeePartyCreditorFinancialAccount/ram:IBANID")
                    if pm is not None
                    else None,
                    "account_name": r.text(pm, "ram:PayeePartyCreditorFinancialAccount/ram:AccountName")
                    if pm is not None
                    else None,
                    "bic": r.text(pm, "ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID")
                    if pm is not None
                    else None,
                    "terms": r.text(st, "ram:SpecifiedTradePaymentTerms/ram:Description"),
                }
            ),
        )
    doc = r.first(root, "rsm:ExchangedDocument")
    header: dict[str, object] = {
        "document_id": document_id,
        "source_format": source_format,
        "seller": _party(r, r.first(agr, "ram:SellerTradeParty") if agr is not None else None, seller=True),
        "buyer": _party(r, r.first(agr, "ram:BuyerTradeParty") if agr is not None else None, seller=False),
        "payment": payment,
        "lines": lines,
        "vat_breakdown": breakdown,
        "totals": totals,
    }
    if doc is not None:
        header |= _clean(
            {
                "invoice_number": r.text(doc, "ram:ID"),
                "issue_date": r.date102(doc, "ram:IssueDateTime/udt:DateTimeString"),
                "type_code": r.text(doc, "ram:TypeCode"),
            }
        )
        header["notes"] = tuple(
            r.raw((n.text or "").strip(), n) for n in r.all(doc, "ram:IncludedNote/ram:Content") if n.text
        )
    if st is not None:
        header |= _clean(
            {
                "currency": r.text(st, "ram:InvoiceCurrencyCode"),
                "due_date": r.date102(
                    st, "ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString"
                ),
            }
        )
    if agr is not None:
        header |= _clean(
            {
                "buyer_reference": r.text(agr, "ram:BuyerReference"),
                "order_reference": r.text(agr, "ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID"),
            }
        )
    if dlv is not None:
        header |= _clean(
            {
                "despatch_advice_reference": r.text(
                    dlv, "ram:DespatchAdviceReferencedDocument/ram:IssuerAssignedID"
                ),
                "delivery_date": r.date102(
                    dlv, "ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString"
                ),
            }
        )
    if st is not None:
        header |= _clean(
            {"preceding_invoice_reference": r.text(st, "ram:InvoiceReferencedDocument/ram:IssuerAssignedID")}
        )
    invoice = r.validated(Invoice, header)
    return ExtractionResult(invoice=invoice, extractor="structured_cii", warnings=tuple(r.warnings))
