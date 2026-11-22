"""Oracle: the expected decision for a labelled case under a tenant config.

This is deliberately a separate, table-driven implementation. The product's
policy gate (Phase 3) is evaluated against it; it must not import or share
code with ``rechnungscheck.policy``.

Rules, most severe first (the first matching rule sets the action):

1. changed bank details             -> escalate, always a human
2. duplicate invoice                -> escalate, always a human
3. compliance (missing mandatory field, arithmetic error, wrong VAT rate)
                                    -> reject_compliance, human
4. no goods receipt yet             -> hold_for_goods_receipt, human
5. expired or short-dated batch     -> request_credit_note, human
6. over-delivery out of tolerance   -> escalate, human
7. short delivery, extra line, over-billed unit mismatch out of tolerance
                                    -> short_pay, human
8. price deviation out of tolerance -> request_credit_note, human
9. missing invoice line             -> approve, human (pay what is invoiced, confirm the rest)
10. only in-tolerance deviations    -> approve_within_tolerance; automatic only if the tenant allows it
                                       and both caps hold
11. clean (rounding within ``rounding_eur`` and exactly convertible unit differences count as clean)
                                    -> approve; automatic if the tenant allows it and the gross cap holds
"""

from __future__ import annotations

from decimal import Decimal

from datagen.models import DiscrepancyLabel, DiscrepancyType, ExpectedOutcome
from rechnungscheck.tenancy import Action, TenantConfig

T = DiscrepancyType
_COMPLIANCE = {T.MISSING_MANDATORY_FIELD, T.ARITHMETIC_ERROR, T.WRONG_VAT_RATE}
_SHORT_PAY = {T.SHORT_DELIVERY, T.EXTRA_LINE, T.UNIT_MISMATCH}
_BENIGN = {T.ROUNDING, T.UNIT_MISMATCH}


def expected_outcome(
    cfg: TenantConfig, labels: tuple[DiscrepancyLabel, ...], gross: Decimal
) -> ExpectedOutcome:
    # Benign: rounding within rounding_eur and a unit difference that converts exactly.
    real = [lb for lb in labels if not (lb.type in _BENIGN and lb.within_tolerance)]
    out = [lb for lb in real if not lb.within_tolerance]
    types = {lb.type for lb in out}
    reasons = tuple(sorted({lb.type.value for lb in out}))

    def human(action: Action) -> ExpectedOutcome:
        return ExpectedOutcome(requires_human=True, action=action, reasons=reasons)

    if T.CHANGED_IBAN in types:
        return human(Action.ESCALATE)
    if T.DUPLICATE_INVOICE in types:
        return human(Action.ESCALATE)
    if types & _COMPLIANCE:
        return human(Action.REJECT_COMPLIANCE)
    if T.NO_GOODS_RECEIPT in types:
        return human(Action.HOLD_FOR_GOODS_RECEIPT)
    if types & {T.EXPIRED_BATCH, T.SHORT_SHELF_LIFE}:
        return human(Action.REQUEST_CREDIT_NOTE)
    if T.OVER_DELIVERY in types:
        return human(Action.ESCALATE)
    if types & _SHORT_PAY:
        return human(Action.SHORT_PAY)
    if T.PRICE_DEVIATION in types:
        return human(Action.REQUEST_CREDIT_NOTE)
    if T.MISSING_LINE in types:
        return human(Action.APPROVE)

    aa = cfg.auto_approval
    gross_ok = aa.max_invoice_gross_eur is None or gross <= aa.max_invoice_gross_eur
    if real:  # only in-tolerance deviations remain
        dev = sum((abs(lb.impact_net_eur) for lb in real), Decimal(0))
        cap_ok = aa.max_total_deviation_eur is not None and dev <= aa.max_total_deviation_eur
        auto = aa.within_tolerance and gross_ok and cap_ok
        why = tuple(sorted({lb.type.value + "_within_tolerance" for lb in real}))
        if not auto:
            why += ("auto_approval_not_allowed" if not aa.within_tolerance else "auto_approval_cap_exceeded",)
        return ExpectedOutcome(requires_human=not auto, action=Action.APPROVE_WITHIN_TOLERANCE, reasons=why)

    auto = aa.clean_invoices and gross_ok
    return ExpectedOutcome(
        requires_human=not auto,
        action=Action.APPROVE,
        reasons=() if auto else ("gross_above_auto_approval_limit",),
    )
