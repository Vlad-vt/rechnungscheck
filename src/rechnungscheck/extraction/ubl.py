"""OASIS UBL 2.1 Invoice (XRechnung UBL) -> canonical invoice."""

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
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
ROOT_TAG = f"{{{NS['inv']}}}Invoice"


def _clean(d: dict[str, Raw | object | None]) -> dict[str, object]:
    return {k: v for k, v in d.items() if v is not None}


def _party(r: XmlReader, el: etree._Element | None, seller: bool) -> Party:
    if el is None:
        return Party()
    addr = r.first(el, "cac:PostalAddress")
    address = None
    if addr is not None:
        address = r.validated(
            PostalAddress,
            _clean(
                {
                    "street": r.text(addr, "cbc:StreetName"),
                    "city": r.text(addr, "cbc:CityName"),
                    "post_code": r.text(addr, "cbc:PostalZone"),
                    "country_code": r.text(addr, "cac:Country/cbc:IdentificationCode"),
                }
            ),
        )
    data: dict[str, object] = _clean(
        {
            "name": r.text(el, "cac:PartyLegalEntity/cbc:RegistrationName")
            or r.text(el, "cac:PartyName/cbc:Name"),
            "vat_id": r.text(el, "cac:PartyTaxScheme[cac:TaxScheme/cbc:ID='VAT']/cbc:CompanyID"),
            "tax_number": r.text(el, "cac:PartyTaxScheme[not(cac:TaxScheme/cbc:ID='VAT')]/cbc:CompanyID")
            if seller
            else None,
            "electronic_address": r.text(el, "cbc:EndpointID"),
            "address": address,
        }
    )
    if seller:
        data |= _clean(
            {
                "contact_name": r.text(el, "cac:Contact/cbc:Name"),
                "contact_phone": r.text(el, "cac:Contact/cbc:Telephone"),
                "contact_email": r.text(el, "cac:Contact/cbc:ElectronicMail"),
            }
        )
    return r.validated(Party, data)


def _line(r: XmlReader, il: etree._Element) -> InvoiceLine:
    data: dict[str, object] = _clean(
        {
            "line_id": r.text(il, "cbc:ID"),
            "order_line_reference": r.text(il, "cac:OrderLineReference/cbc:LineID"),
            "item_name": r.text(il, "cac:Item/cbc:Name"),
            "seller_item_id": r.text(il, "cac:Item/cac:SellersItemIdentification/cbc:ID"),
            "buyer_item_id": r.text(il, "cac:Item/cac:BuyersItemIdentification/cbc:ID"),
            "gtin": r.text(il, "cac:Item/cac:StandardItemIdentification/cbc:ID[@schemeID='0160']"),
            "quantity": r.decimal(il, "cbc:InvoicedQuantity"),
            "net_price": r.decimal(il, "cac:Price/cbc:PriceAmount"),
            "price_base_quantity": r.decimal(il, "cac:Price/cbc:BaseQuantity"),
            "line_net_amount": r.decimal(il, "cbc:LineExtensionAmount"),
            "vat_category": r.text(il, "cac:Item/cac:ClassifiedTaxCategory/cbc:ID"),
            "vat_rate": r.decimal(il, "cac:Item/cac:ClassifiedTaxCategory/cbc:Percent"),
        }
    )
    qty_el = r.first(il, "cbc:InvoicedQuantity")
    if qty_el is not None and qty_el.get("unitCode"):
        data["unit_code"] = r.raw(qty_el.get("unitCode"), qty_el)
    data |= parse_line_note(r, r.first(il, "cbc:Note"))
    return r.validated(InvoiceLine, data)


def parse_ubl(data: bytes, document_id: str, locator_prefix: str = "") -> ExtractionResult:
    root = parse_xml(data)
    if root.tag != ROOT_TAG:
        raise ValueError(f"not a UBL invoice: root element {root.tag}")
    r = XmlReader(root, NS, evidence_prefix=document_id, locator_prefix=locator_prefix)
    pm = r.first(root, "cac:PaymentMeans")
    tt = r.first(root, "cac:TaxTotal")
    lmt = r.first(root, "cac:LegalMonetaryTotal")
    breakdown = tuple(
        r.validated(
            VatBreakdown,
            _clean(
                {
                    "category": r.text(s, "cac:TaxCategory/cbc:ID"),
                    "rate": r.decimal(s, "cac:TaxCategory/cbc:Percent"),
                    "taxable_amount": r.decimal(s, "cbc:TaxableAmount"),
                    "tax_amount": r.decimal(s, "cbc:TaxAmount"),
                    "exemption_reason": r.text(s, "cac:TaxCategory/cbc:TaxExemptionReason"),
                }
            ),
        )
        for s in (r.all(tt, "cac:TaxSubtotal") if tt is not None else [])
    )
    totals = DocumentTotals()
    if lmt is not None:
        totals = r.validated(
            DocumentTotals,
            _clean(
                {
                    "sum_of_line_net": r.decimal(lmt, "cbc:LineExtensionAmount"),
                    "allowances": r.decimal(lmt, "cbc:AllowanceTotalAmount"),
                    "charges": r.decimal(lmt, "cbc:ChargeTotalAmount"),
                    "total_without_vat": r.decimal(lmt, "cbc:TaxExclusiveAmount"),
                    "total_vat": r.decimal(tt, "cbc:TaxAmount") if tt is not None else None,
                    "total_with_vat": r.decimal(lmt, "cbc:TaxInclusiveAmount"),
                    "prepaid": r.decimal(lmt, "cbc:PrepaidAmount"),
                    "rounding": r.decimal(lmt, "cbc:PayableRoundingAmount"),
                    "amount_due": r.decimal(lmt, "cbc:PayableAmount"),
                }
            ),
        )
    payment = r.validated(
        PaymentInstructions,
        _clean(
            {
                "means_code": r.text(pm, "cbc:PaymentMeansCode") if pm is not None else None,
                "iban": r.text(pm, "cac:PayeeFinancialAccount/cbc:ID") if pm is not None else None,
                "account_name": r.text(pm, "cac:PayeeFinancialAccount/cbc:Name") if pm is not None else None,
                "bic": r.text(pm, "cac:PayeeFinancialAccount/cac:FinancialInstitutionBranch/cbc:ID")
                if pm is not None
                else None,
                "terms": r.text(root, "cac:PaymentTerms/cbc:Note"),
            }
        ),
    )
    header: dict[str, object] = {
        "document_id": document_id,
        "source_format": SourceFormat.XRECHNUNG_UBL,
        "seller": _party(r, r.first(root, "cac:AccountingSupplierParty/cac:Party"), seller=True),
        "buyer": _party(r, r.first(root, "cac:AccountingCustomerParty/cac:Party"), seller=False),
        "payment": payment,
        "lines": tuple(_line(r, il) for il in r.all(root, "cac:InvoiceLine")),
        "vat_breakdown": breakdown,
        "totals": totals,
        "notes": tuple(r.raw((n.text or "").strip(), n) for n in r.all(root, "cbc:Note") if n.text),
    }
    header |= _clean(
        {
            "invoice_number": r.text(root, "cbc:ID"),
            "issue_date": r.iso_date(root, "cbc:IssueDate"),
            "type_code": r.text(root, "cbc:InvoiceTypeCode"),
            "currency": r.text(root, "cbc:DocumentCurrencyCode"),
            "due_date": r.iso_date(root, "cbc:DueDate"),
            "buyer_reference": r.text(root, "cbc:BuyerReference"),
            "order_reference": r.text(root, "cac:OrderReference/cbc:ID"),
            "despatch_advice_reference": r.text(root, "cac:DespatchDocumentReference/cbc:ID"),
            "preceding_invoice_reference": r.text(
                root, "cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID"
            ),
            "delivery_date": r.iso_date(root, "cac:Delivery/cbc:ActualDeliveryDate"),
        }
    )
    return ExtractionResult(
        invoice=r.validated(Invoice, header), extractor="structured_ubl", warnings=tuple(r.warnings)
    )
