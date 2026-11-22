"""Tenant configuration schema.

One YAML file per tenant (``tenants/<tenant_id>/config.yaml``), validated by
these models. Onboarding a tenant means adding a directory, never code.

Invariants that are deliberately NOT configurable, so no tenant config can
weaken them (``extra="forbid"`` rejects any attempt to add such a key):

* Changed bank details always go to a human.
* Suspected duplicate invoices always go to a human.
* An LLM never decides whether an invoice may be approved; the policy gate is code.
* ``tenant_id`` at runtime comes from authentication, never from this file
  or a model. The file's ``tenant_id`` only has to match its directory.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from rechnungscheck.domain.invoice import INVOICE_FIELD_PATHS
from rechnungscheck.domain.types import UnitCode

TenantId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{2,31}$")]
TierName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,31}$")]
NonNegDecimal = Annotated[Decimal, Field(ge=0)]
Fraction = Annotated[Decimal, Field(ge=0, le=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Language(StrEnum):
    DE = "de"
    EN = "en"


class ModelRole(StrEnum):
    """Every place in the system that calls a model."""

    EXTRACTOR = "extractor"
    """Vision extraction of PDFs, scans and delivery notes. Needs a vision tier."""
    COMPLIANCE_EXPLAINER = "compliance_explainer"
    """Explains code-detected rule violations in the tenant language."""
    LINE_MATCHER = "line_matcher"
    """Matches only the lines deterministic matching could not."""
    INVESTIGATOR = "investigator"
    RESOLUTION_PLANNER = "resolution_planner"
    CORRESPONDENCE_WRITER = "correspondence_writer"
    FACT_CHECK_WORDING = "fact_check_wording"
    BASELINE_AGENT = "baseline_agent"
    """Single-agent ReAct baseline used for the comparison eval."""


class ModelTier(_Strict):
    """A Foundry model deployment."""

    deployment: str = Field(min_length=1, description="Foundry deployment name.")
    model: str = Field(min_length=1, description="Model name, for reporting and cost lookup.")
    vision: bool = Field(default=False, description="Accepts image input (verified, see PREFLIGHT.md).")
    fallback: TierName | None = Field(default=None, description="Tier used by the model-fallback middleware.")


class EmbeddingModel(_Strict):
    deployment: str = Field(min_length=1)
    model: str = Field(min_length=1)


class ModelMapping(_Strict):
    tiers: dict[TierName, ModelTier] = Field(min_length=1)
    roles: dict[ModelRole, TierName]
    embedding: EmbeddingModel

    @model_validator(mode="after")
    def _check(self) -> Self:
        missing = set(ModelRole) - set(self.roles)
        if missing:
            raise ValueError(f"roles without a tier: {sorted(missing)}")
        for role, tier_name in self.roles.items():
            if tier_name not in self.tiers:
                raise ValueError(f"role {role.value!r} uses unknown tier {tier_name!r}")
        if not self.tiers[self.roles[ModelRole.EXTRACTOR]].vision:
            raise ValueError("the extractor role must use a vision-capable tier")
        for name, tier in self.tiers.items():
            seen = {name}
            nxt = tier.fallback
            while nxt is not None:
                if nxt not in self.tiers:
                    raise ValueError(f"tier {name!r} falls back to unknown tier {nxt!r}")
                if nxt in seen:
                    raise ValueError(f"fallback cycle starting at tier {name!r}")
                seen.add(nxt)
                nxt = self.tiers[nxt].fallback
        return self


class Tolerance(_Strict):
    """A deviation is within tolerance if it is within EITHER bound."""

    relative: Fraction = Field(default=Decimal(0), description="Fraction of the expected value, 0.02 = 2 %.")
    absolute: NonNegDecimal = Field(default=Decimal(0), description="Absolute amount in the value's unit.")


class Tolerances(_Strict):
    quantity: Tolerance = Field(default_factory=Tolerance, description="Default for all units.")
    quantity_by_unit: dict[UnitCode, Tolerance] = Field(
        default_factory=dict, description="Overrides per unit code, e.g. KGM for weighed goods."
    )
    unit_price: Tolerance = Field(default_factory=Tolerance, description="Absolute part in EUR.")
    rounding_eur: NonNegDecimal = Field(
        default=Decimal("0.01"), le=Decimal("0.05"), description="Accepted rounding difference per total."
    )


class ShelfLife(_Strict):
    min_remaining_days: int = Field(
        ge=0, description="Minimum days between delivery date and best-before date. 0 = not expired."
    )


class Action(StrEnum):
    """Resolution actions. Each tenant enables a subset."""

    APPROVE = "approve"
    APPROVE_WITHIN_TOLERANCE = "approve_within_tolerance"
    SHORT_PAY = "short_pay"
    REQUEST_CREDIT_NOTE = "request_credit_note"
    REJECT_COMPLIANCE = "reject_compliance"
    HOLD_FOR_GOODS_RECEIPT = "hold_for_goods_receipt"
    ESCALATE = "escalate"


class AutoApproval(_Strict):
    """When the policy gate may approve without a human. Everything else goes to review."""

    clean_invoices: bool = Field(description="Auto-approve invoices with no discrepancy at all.")
    within_tolerance: bool = Field(
        description="Auto-approve invoices whose discrepancies are all in tolerance."
    )
    max_invoice_gross_eur: NonNegDecimal | None = Field(
        default=None, description="No auto-approval above this gross total. None = no limit."
    )
    max_total_deviation_eur: NonNegDecimal | None = Field(
        default=None, description="Cap on the summed absolute monetary impact of in-tolerance deviations."
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.within_tolerance and self.max_total_deviation_eur is None:
            raise ValueError("within_tolerance auto-approval needs max_total_deviation_eur")
        return self


class Reviewer(_Strict):
    reviewer_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,63}$")
    display_name: str = Field(min_length=1)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Budget(_Strict):
    daily_token_limit: int = Field(gt=0)
    daily_cost_limit_eur: Decimal = Field(gt=0)


class TenantConfig(_Strict):
    schema_version: Literal[1]
    tenant_id: TenantId
    display_name: str = Field(min_length=1)
    business: str = Field(min_length=1, description="Short description, used in prompts.")
    language: Language = Field(description="Language of explanations, reports and default correspondence.")
    correspondence_languages: tuple[Language, ...] = Field(min_length=1)
    currency: Literal["EUR"] = "EUR"
    models: ModelMapping
    mandatory_fields: tuple[str, ...] = Field(
        default=(), description="Tenant-specific mandatory invoice fields, as INVOICE_FIELD_PATHS."
    )
    tolerances: Tolerances = Field(default_factory=Tolerances)
    shelf_life: ShelfLife | None = None
    actions: tuple[Action, ...] = Field(min_length=1)
    auto_approval: AutoApproval
    reviewers: tuple[Reviewer, ...] = Field(min_length=1)
    budget: Budget

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.language not in self.correspondence_languages:
            raise ValueError("language must be one of correspondence_languages")
        unknown = sorted(set(self.mandatory_fields) - INVOICE_FIELD_PATHS)
        if unknown:
            raise ValueError(f"unknown mandatory_fields: {unknown}")
        if len(set(self.mandatory_fields)) != len(self.mandatory_fields):
            raise ValueError("duplicate entries in mandatory_fields")
        if len(set(self.actions)) != len(self.actions):
            raise ValueError("duplicate entries in actions")
        if Action.ESCALATE not in self.actions:
            raise ValueError("actions must include 'escalate'")
        if self.auto_approval.clean_invoices and Action.APPROVE not in self.actions:
            raise ValueError("auto-approving clean invoices needs the 'approve' action")
        if self.auto_approval.within_tolerance and Action.APPROVE_WITHIN_TOLERANCE not in self.actions:
            raise ValueError("auto-approving within tolerance needs the 'approve_within_tolerance' action")
        if self.shelf_life is not None and "lines[].best_before_date" not in self.mandatory_fields:
            raise ValueError("a shelf_life rule needs 'lines[].best_before_date' in mandatory_fields")
        ids = [r.reviewer_id for r in self.reviewers]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate reviewer_id")
        return self
