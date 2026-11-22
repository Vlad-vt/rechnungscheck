# Tenant onboarding

A tenant is data, not code. Adding one means adding a directory.

```
tenants/<tenant_id>/
  config.yaml      validated by rechnungscheck.tenancy.TenantConfig
  master_data/     suppliers, products, price agreements (Phase 2)
  contracts/       synthetic supplier contracts for the knowledge base (Phase 2)
  evals/           tenant eval set and thresholds (Phase 4)
```

## Steps (current state: Phase 1)

1. Copy an existing tenant directory and rename it. The directory name **is** the tenant id: lowercase, 3 to 32 characters, `[a-z][a-z0-9-]*`.
2. Edit `config.yaml`. Print the full schema with `uv run rechnungscheck tenants schema`.
3. Run `uv run rechnungscheck tenants validate` (CI runs the same command).

## What the schema enforces

- `tenant_id` equals the directory name.
- Every model role is mapped to a defined tier; the extractor tier must have `vision: true`; fallbacks reference existing tiers and contain no cycles.
- `mandatory_fields` only uses paths from `INVOICE_FIELD_PATHS`, for example `buyer_reference` or `lines[].serial_numbers`.
- Relative tolerances are fractions (0..1); rounding tolerance is at most EUR 0.05.
- `actions` contains `escalate`. Auto-approving clean invoices requires `approve`, and auto-approving within tolerance requires `approve_within_tolerance` plus a `max_total_deviation_eur` cap.
- A `shelf_life` rule requires `lines[].best_before_date` to be mandatory.
- `language` is one of `correspondence_languages`.
- Unknown keys are rejected anywhere in the file.

## What a tenant cannot configure

These invariants are deliberately not configurable:

- Changed bank details always go to a human.
- Suspected duplicates always go to a human.
- Approval is decided by code, never by a model.

Any attempt to add a key for them fails validation; a test proves it.

This document grows with master data (Phase 2), eval sets (Phase 4) and deployment-time steps (Phase 5). The goal for Phase 8 is a fourth tenant added in a single commit with no code change.
