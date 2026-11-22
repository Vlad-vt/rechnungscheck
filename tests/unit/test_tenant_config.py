import copy
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from rechnungscheck.cli import app
from rechnungscheck.tenancy import Action, ModelRole, TenantConfig, TenantConfigError, load_all, load_tenant

TENANTS_ROOT = Path(__file__).resolve().parents[2] / "tenants"
DEMO_TENANTS = ("frischemarkt", "technikhaus", "drogeriewelt")


@pytest.fixture
def base() -> dict[str, Any]:
    raw = yaml.safe_load((TENANTS_ROOT / "frischemarkt" / "config.yaml").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def _invalid(raw: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        TenantConfig.model_validate(raw)


# --- the committed demo tenants -------------------------------------------------


def test_all_demo_tenants_load():
    result = load_all(TENANTS_ROOT)
    assert result.errors == []
    assert set(DEMO_TENANTS) <= set(result.tenants)


def test_frischemarkt_rules():
    t = load_tenant(TENANTS_ROOT / "frischemarkt")
    assert {"lines[].batch_number", "lines[].best_before_date"} <= set(t.mandatory_fields)
    assert t.tolerances.quantity_by_unit["KGM"].relative == Decimal("0.02")
    assert t.auto_approval.within_tolerance is True


def test_technikhaus_rules():
    t = load_tenant(TENANTS_ROOT / "technikhaus")
    assert "lines[].serial_numbers" in t.mandatory_fields
    assert t.tolerances.quantity.relative == 0
    assert t.tolerances.quantity.absolute == 0
    assert t.tolerances.unit_price.relative == 0
    assert t.tolerances.unit_price.absolute == 0
    assert t.auto_approval.within_tolerance is False
    assert {lang.value for lang in t.correspondence_languages} == {"de", "en"}


def test_drogeriewelt_sends_every_discrepancy_to_a_human():
    t = load_tenant(TENANTS_ROOT / "drogeriewelt")
    assert t.auto_approval.within_tolerance is False
    assert Action.APPROVE_WITHIN_TOLERANCE not in t.actions
    assert t.shelf_life is not None
    assert t.shelf_life.min_remaining_days > 0


@pytest.mark.parametrize("tenant", DEMO_TENANTS)
def test_demo_reviewers_use_reserved_example_domains(tenant):
    t = load_tenant(TENANTS_ROOT / tenant)
    for r in t.reviewers:
        assert r.email.endswith(".example"), r.email


def test_yaml_decimals_are_exact():
    t = load_tenant(TENANTS_ROOT / "frischemarkt")
    assert t.tolerances.rounding_eur == Decimal("0.02")
    assert t.budget.daily_cost_limit_eur == Decimal("1.00")


# --- schema rules ---------------------------------------------------------------


def test_non_configurable_invariants_cannot_be_added(base):
    for key in ("auto_approve_bank_detail_changes", "allow_duplicates", "approve_by_llm"):
        raw = copy.deepcopy(base)
        raw["auto_approval"][key] = True
        _invalid(raw, "Extra inputs are not permitted")


def test_every_model_role_must_be_mapped(base):
    del base["models"]["roles"][ModelRole.INVESTIGATOR.value]
    _invalid(base, "roles without a tier")


def test_role_must_reference_existing_tier(base):
    base["models"]["roles"]["investigator"] = "huge"
    _invalid(base, "unknown tier")


def test_extractor_needs_vision(base):
    base["models"]["tiers"]["strong"]["vision"] = False
    _invalid(base, "vision-capable")


def test_fallback_cycle_is_rejected(base):
    base["models"]["tiers"]["small"]["fallback"] = "strong"
    _invalid(base, "fallback cycle")


def test_unknown_fallback_is_rejected(base):
    base["models"]["tiers"]["strong"]["fallback"] = "tiny"
    _invalid(base, "unknown tier")


def test_unknown_mandatory_field_is_rejected(base):
    base["mandatory_fields"].append("lines[].colour")
    _invalid(base, "unknown mandatory_fields")


def test_escalate_is_always_available(base):
    base["actions"].remove("escalate")
    _invalid(base, "must include 'escalate'")


def test_auto_approval_needs_matching_action(base):
    base["actions"].remove("approve_within_tolerance")
    _invalid(base, "approve_within_tolerance")


def test_within_tolerance_needs_deviation_cap(base):
    del base["auto_approval"]["max_total_deviation_eur"]
    _invalid(base, "max_total_deviation_eur")


@pytest.mark.parametrize("value", [-0.01, 1.5])
def test_relative_tolerance_is_a_fraction(base, value):
    base["tolerances"]["quantity"]["relative"] = value
    _invalid(base, "relative")


def test_rounding_tolerance_is_capped(base):
    base["tolerances"]["rounding_eur"] = 0.5
    _invalid(base, "rounding_eur")


def test_shelf_life_needs_best_before_field(base):
    base["mandatory_fields"].remove("lines[].best_before_date")
    _invalid(base, "best_before_date")


def test_language_must_be_a_correspondence_language(base):
    base["correspondence_languages"] = ["en"]
    _invalid(base, "correspondence_languages")


def test_tenant_id_format(base):
    base["tenant_id"] = "Frische Markt"
    _invalid(base, "tenant_id")


# --- loader ---------------------------------------------------------------------


def test_tenant_id_must_match_directory(tmp_path, base):
    d = tmp_path / "other-tenant"
    d.mkdir()
    (d / "config.yaml").write_text(yaml.safe_dump(base), encoding="utf-8")
    with pytest.raises(TenantConfigError, match="does not match directory"):
        load_tenant(d)


def test_load_all_collects_every_error(tmp_path, base):
    good = tmp_path / "frischemarkt"
    good.mkdir()
    (good / "config.yaml").write_text(yaml.safe_dump(base), encoding="utf-8")
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "config.yaml").write_text("tenant_id: [", encoding="utf-8")
    (tmp_path / "empty").mkdir()
    result = load_all(tmp_path)
    assert set(result.tenants) == {"frischemarkt"}
    assert {e.tenant_dir.name for e in result.errors} == {"broken", "empty"}
    assert not result.ok


def test_cli_validate_succeeds_on_demo_tenants():
    res = CliRunner().invoke(app, ["tenants", "validate", "--dir", str(TENANTS_ROOT)])
    assert res.exit_code == 0, res.output
    assert "tenant config(s) valid" in res.output  # count-agnostic: a new tenant needs no test change


def test_cli_validate_fails_on_invalid_tenant(tmp_path):
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "config.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    res = CliRunner().invoke(app, ["tenants", "validate", "--dir", str(tmp_path)])
    assert res.exit_code == 1
