# Tenant onboarding

A tenant is data, not code. Adding one means adding a directory.

```
tenants/<tenant_id>/
  config.yaml      validated by rechnungscheck.tenancy.TenantConfig
  datagen.yaml     demo tenants only: seed for the synthetic generator (buyer, suppliers, products)
  master_data/     suppliers, products, unit conversions, price agreements, invoice history (JSON)
  contracts/       supplier framework contracts (Markdown) for the knowledge base
  evals/           cases.jsonl (labelled cases), dataset.json, documents.sha256; thresholds in Phase 4
```

## Steps (current state: Phase 2)

1. Copy an existing tenant directory and rename it. The directory name **is** the tenant id: lowercase, 3 to 32 characters, `[a-z][a-z0-9-]*`.
2. Edit `config.yaml`. Print the full schema with `uv run rechnungscheck tenants schema`.
3. Run `uv run rechnungscheck tenants validate` (CI runs the same command).
4. Demo tenant: write `datagen.yaml` (schema: `datagen.catalog.TenantSeed`; exactly one supplier is
   `shared: true`, the cross-tenant probe supplier), then `make data`. This writes `master_data/`,
   `contracts/` and `evals/` and renders the documents into `data/generated/<tenant_id>/`.
   A real tenant instead supplies `master_data/` and `contracts/` directly.

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
