import random
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from datagen import ids
from datagen.catalog import TenantSeed, load_seed
from datagen.contracts import render_contracts
from datagen.labels import expected_outcome
from datagen.masterdata import build_master_data
from datagen.models import DiscrepancyLabel, DiscrepancyType, Split
from datagen.scenarios import SCENARIOS, generate_cases
from rechnungscheck.tenancy import Action, load_all

TENANTS = Path(__file__).resolve().parents[2] / "tenants"
SEED = 42
SHARED_NAME = "Kranichfeld Handelskontor GmbH"


@pytest.fixture(scope="module")
def tenants():
    res = load_all(TENANTS)
    assert res.ok
    return res.tenants


@pytest.fixture(scope="module")
def generated(tenants):
    out = {}
    for tid, cfg in tenants.items():
        md = build_master_data(tid, load_seed(TENANTS / tid), SEED)
        out[tid] = (cfg, md, *generate_cases(cfg, md, load_seed(TENANTS / cfg.tenant_id).buyer, SEED))
    return out


# --- identifiers -------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(20))
def test_synthetic_identifiers_are_valid_and_in_reserved_ranges(seed):
    rng = random.Random(seed)
    gtin = ids.make_gtin(rng)
    assert ids.gtin_is_valid(gtin)
    assert gtin.startswith("2")  # GS1 restricted-circulation prefix 200-299
    iban = ids.make_de_iban(rng)
    assert ids.iban_is_valid(iban)
    assert iban[4:6] == "99"  # fictitious bank code range
    vat = ids.make_de_vat_id(rng)
    assert vat.startswith("DE99")
    assert ids.de_vat_check_digit(vat[2:10]) == int(vat[10])


def test_iban_check_rejects_a_typo():
    iban = ids.make_de_iban(random.Random(1))
    typo = iban[:-1] + str((int(iban[-1]) + 1) % 10)
    assert not ids.iban_is_valid(typo)


# --- dataset shape -----------------------------------------------------------------


def test_generation_is_deterministic(tenants):
    cfg = tenants["frischemarkt"]
    md1, md2 = (
        build_master_data("frischemarkt", load_seed(TENANTS / "frischemarkt"), SEED),
        build_master_data("frischemarkt", load_seed(TENANTS / "frischemarkt"), SEED),
    )
    assert md1 == md2
    a, _ = generate_cases(cfg, md1, load_seed(TENANTS / cfg.tenant_id).buyer, SEED)
    b, _ = generate_cases(cfg, md2, load_seed(TENANTS / cfg.tenant_id).buyer, SEED)
    assert [c.model_dump_json() for c in a] == [c.model_dump_json() for c in b]


def test_at_least_200_cases_with_balanced_split(generated):
    cases = [c for _, _, cs, _ in generated.values() for c in cs]
    assert len(cases) >= 200
    for tid, (_, _, cs, _) in generated.items():
        split = Counter(c.split for c in cs)
        assert abs(split[Split.DEV] - split[Split.TEST]) <= 1, tid


def test_every_scenario_appears_in_both_splits_per_tenant(generated):
    for tid, (_, _, cs, _) in generated.items():
        for name, (_, count) in SCENARIOS.items():
            splits = {c.split for c in cs if c.scenario == name}
            if count >= 2:
                assert splits == {Split.DEV, Split.TEST}, (tid, name)


def test_expected_actions_are_in_the_tenant_catalogue(generated):
    for cfg, _, cs, _ in generated.values():
        for c in cs:
            assert c.expected.action in cfg.actions, c.case_id


def test_non_clean_scenarios_carry_labels(generated):
    for _, _, cs, _ in generated.values():
        for c in cs:
            if c.scenario != "clean":
                assert c.labels, c.case_id


def test_safety_cases_always_need_a_human(generated):
    for _, _, cs, _ in generated.values():
        for c in cs:
            types = {lb.type for lb in c.labels}
            if types & {DiscrepancyType.CHANGED_IBAN, DiscrepancyType.DUPLICATE_INVOICE}:
                assert c.expected.requires_human, c.case_id
                assert c.expected.action is Action.ESCALATE


def test_duplicates_are_in_the_invoice_history(generated):
    for _, _, cs, history in generated.values():
        seen = {(h.supplier_id, h.invoice_number) for h in history}
        for c in cs:
            if any(lb.type is DiscrepancyType.DUPLICATE_INVOICE for lb in c.labels):
                assert c.invoice.invoice_number is not None
                assert (c.purchase_order.supplier_id, c.invoice.invoice_number.value) in seen


def test_changed_iban_differs_from_master_data(generated):
    for _, md, cs, _ in generated.values():
        ibans = {s.supplier_id: s.iban for s in md.suppliers}
        for c in cs:
            assert c.invoice.payment.iban is not None
            changed = any(lb.type is DiscrepancyType.CHANGED_IBAN for lb in c.labels)
            same = c.invoice.payment.iban.value == ibans[c.purchase_order.supplier_id]
            assert changed != same, c.case_id


def test_injections_exist_and_do_not_change_the_label_logic(generated):
    injected = [c for _, _, cs, _ in generated.values() for c in cs if c.injection.value != "none"]
    assert len(injected) >= 20
    for c in injected:
        assert c.injection_text


def test_no_goods_receipt_cases_have_no_delivery_note(generated):
    for _, _, cs, _ in generated.values():
        for c in cs:
            no_gr = any(lb.type is DiscrepancyType.NO_GOODS_RECEIPT for lb in c.labels)
            assert (c.delivery_note is None) == no_gr, c.case_id


def test_frischemarkt_has_touchless_in_tolerance_cases(generated):
    _, _, cs, _ = generated["frischemarkt"]
    auto_tol = [
        c
        for c in cs
        if c.expected.action is Action.APPROVE_WITHIN_TOLERANCE and not c.expected.requires_human
    ]
    assert auto_tol


def test_drogeriewelt_sends_every_real_discrepancy_to_a_human(generated):
    _, _, cs, _ = generated["drogeriewelt"]
    for c in cs:
        benign = all(
            lb.type in {DiscrepancyType.ROUNDING, DiscrepancyType.UNIT_MISMATCH} and lb.within_tolerance
            for lb in c.labels
        )
        if c.labels and not benign:
            assert c.expected.requires_human, c.case_id


# --- oracle rules ------------------------------------------------------------------


def test_oracle_gross_limit_blocks_auto_approval(tenants):
    cfg = tenants["drogeriewelt"]
    limit = cfg.auto_approval.max_invoice_gross_eur
    assert limit is not None
    assert not expected_outcome(cfg, (), limit).requires_human
    assert expected_outcome(cfg, (), limit + 1).requires_human


def test_oracle_bank_change_beats_everything(tenants):
    cfg = tenants["frischemarkt"]
    labels = (
        DiscrepancyLabel(type=DiscrepancyType.SHORT_DELIVERY, within_tolerance=True),
        DiscrepancyLabel(type=DiscrepancyType.CHANGED_IBAN),
    )
    out = expected_outcome(cfg, labels, cfg.auto_approval.max_invoice_gross_eur or Decimal(0))
    assert out.requires_human
    assert out.action is Action.ESCALATE


# --- master data and contracts -----------------------------------------------------


def test_shared_supplier_has_different_bank_details_per_tenant(tenants):
    ibans = set()
    for tid in tenants:
        md = build_master_data(tid, load_seed(TENANTS / tid), SEED)
        shared = [s for s in md.suppliers if s.name == SHARED_NAME]
        assert len(shared) == 1, tid
        ibans.add(shared[0].iban)
    assert len(ibans) == len(tenants)


def test_contracts_exist_per_supplier_and_differ_across_tenants(tenants):
    shared_texts = set()
    for tid, cfg in tenants.items():
        md = build_master_data(tid, load_seed(TENANTS / tid), SEED)
        contracts = render_contracts(cfg, load_seed(TENANTS / tid), md)
        assert len(contracts) == len(md.suppliers)
        shared_texts |= {t for t in contracts.values() if SHARED_NAME in t}
    assert len(shared_texts) == len(tenants)


# --- generator seed (tenants/<id>/datagen.yaml) ------------------------------------


def _seed_raw(tid="frischemarkt"):
    return yaml.safe_load((TENANTS / tid / "datagen.yaml").read_text(encoding="utf-8"))


def test_every_demo_tenant_has_a_valid_seed(tenants):
    for tid in tenants:
        assert load_seed(TENANTS / tid).suppliers


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r["suppliers"][0].update(shared=True), "exactly one supplier"),
        (lambda r: r["products"][0].update(supplier=99), "supplier index"),
        (lambda r: r["products"][0].update(unit="XCT"), "pack_size"),
        (lambda r: r["products"][0].update(colour="red"), "Extra inputs"),
    ],
)
def test_invalid_seed_is_rejected(mutate, message):
    raw = _seed_raw()
    mutate(raw)
    with pytest.raises(ValidationError, match=message):
        TenantSeed.model_validate(raw)
