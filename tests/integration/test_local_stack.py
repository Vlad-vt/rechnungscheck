"""Needs the Docker Compose stack: ``docker compose up -d --wait`` (``make up``)."""

import os
import socket
from pathlib import Path

import pytest
from lxml import etree

from datagen.catalog import load_seed
from datagen.masterdata import build_master_data
from datagen.render.cii import render_cii
from datagen.render.ubl import render_ubl
from datagen.scenarios import generate_cases
from rechnungscheck.compliance.validator_client import KositClient, Verdict
from rechnungscheck.tenancy import load_tenant

pytestmark = pytest.mark.integration

KOSIT_URL = os.environ.get("KOSIT_URL", "http://127.0.0.1:8081")
TENANTS = Path(__file__).resolve().parents[2] / "tenants"


@pytest.fixture(scope="module")
def kosit():
    client = KositClient(KOSIT_URL)
    if not client.healthy():
        pytest.fail(f"KoSIT validator not reachable at {KOSIT_URL}; run `make up`")
    return client


@pytest.fixture(scope="module")
def clean_case():
    cfg = load_tenant(TENANTS / "frischemarkt")
    md = build_master_data("frischemarkt", load_seed(TENANTS / "frischemarkt"), 42)
    cases, _ = generate_cases(cfg, md, load_seed(TENANTS / cfg.tenant_id).buyer, 42)
    return next(c for c in cases if c.scenario == "clean")


def test_clean_xrechnung_cii_and_ubl_are_accepted(kosit, clean_case):
    for xml in (render_cii(clean_case.invoice, "de"), render_ubl(clean_case.invoice, "de")):
        report = kosit.validate(xml)
        assert report.verdict is Verdict.ACCEPT, [m.code for m in report.errors]
        assert report.scenario is not None
        assert "XRechnung" in report.scenario


def test_missing_buyer_reference_violates_br_de_15(kosit, clean_case):
    inv = clean_case.invoice.model_copy(update={"buyer_reference": None})
    report = kosit.validate(render_ubl(inv, "de"))
    assert report.verdict is Verdict.REJECT
    assert "BR-DE-15" in {m.code for m in report.errors}


def test_wrong_total_violates_br_co_15(kosit, clean_case):
    root = etree.fromstring(render_cii(clean_case.invoice, "de"))
    ns = {"ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"}
    grand = root.xpath("//ram:GrandTotalAmount", namespaces=ns)[0]
    grand.text = "99999.99"
    report = kosit.validate(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    assert report.verdict is Verdict.REJECT
    assert "BR-CO-15" in {m.code for m in report.errors}


def test_unknown_profile_is_unsupported_not_invalid(kosit, clean_case):
    xml = render_cii(clean_case.invoice, "de", profile="en16931").replace(
        b"urn:cen.eu:en16931:2017<", b"urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended<"
    )
    assert kosit.validate(xml).verdict is Verdict.UNSUPPORTED


@pytest.mark.parametrize(("host", "port"), [("127.0.0.1", 5432), ("127.0.0.1", 10000)])
def test_postgres_and_azurite_are_listening(host, port):
    with socket.create_connection((host, port), timeout=5):
        pass
