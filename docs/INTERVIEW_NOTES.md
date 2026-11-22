# Interview notes

For each component: what it does, why it was chosen, alternatives, trade-offs, measured numbers. Only measured numbers appear here; anything not yet measured says so.

## Phase 0: preflight (docs/PREFLIGHT.md)

- **What:** found out what the Azure for Students subscription allows before designing anything.
- **Key findings:**
  - A deny policy limits deployments to 5 regions.
  - Postgres Flexible Server provisioning is restricted in `germanywestcentral`, which led to ADR 0001.
  - Foundry models, image input, Document Intelligence and Prompt Shields work keylessly on one AIServices account.
- **Lesson worth telling:** ARM `validate` is weaker evidence than it looks. Two negative controls proved it: an over-quota model deployment (capacity 900000 against a 1000 limit) passed, and Postgres in the restricted region passed. `validate` does catch the region policy. Quota and regional capability need their own APIs, or a real deployment.
- **Measured:** single smoke calls only, for example image extraction of a synthetic invoice that was correct on both `gpt-5.4-mini` and `gpt-5.5`. These are not benchmarks. Latency and cost get measured in Phase 4.

## Canonical invoice model (src/rechnungscheck/domain, ADR 0002)

- **What:** one EN 16931-subset model that every extractor produces. Each field is `Extracted[T]`: value, confidence, evidence.
- **Why:** compliance, matching, the Fact Checker and the evals stay independent of the input format and the extractor. Evidence ids make "every figure traces to evidence" checkable by code.
- **Trade-offs:** all fields are optional, because the model records extraction and not validity, so callers must handle `None`. It is verbose to access. There is no arithmetic in the model; recomputation happens in compliance.
- **Alternatives:** XML tree as the model; a library model such as `drafthorse`; a flat model with a separate evidence map. Reasons in ADR 0002.
- **Measured:** nothing yet (extraction accuracy comes in Phase 4).

## Tenant configuration (src/rechnungscheck/tenancy)

- **What:** a YAML file per tenant, validated by a strict Pydantic schema, loaded by directory name.
- **Why:** onboarding without code changes, and a typo in a tenant config fails CI instead of failing at runtime. Cross-field rules are enforced: role to tier mapping, vision for the extractor, fallback cycles, mandatory fields against the invoice model, actions against auto-approval settings.
- **Security angle:** invariants such as "changed IBAN always goes to a human" are not keys in the schema at all. With `extra="forbid"` a config cannot even express weakening them, and a test proves it.
- **Alternatives:** a database table (needs migrations and an admin UI, harder to review); JSON (no comments); environment variables (no structure).
- **Measured:** nothing yet.

## CI (.github/workflows/ci.yml)

- **What:** ruff, mypy strict, unit tests, tenant validation, Bicep lint, checkov, gitleaks, pip-audit. No cloud credentials.
- **Choices:**
  - Actions are pinned by commit SHA, and Dependabot updates them.
  - gitleaks runs as the MIT CLI with a verified SHA-256, not through `gitleaks-action`, which ships under a separate end-user licence.
  - pip-audit audits the exported lockfile with hashes (`--disable-pip`), so it checks exactly what is locked.
  - The preflight Bicep probes are linted but excluded from checkov, because they are never deployed. A full scan of them reports 17 failed checks, as expected for throwaway probes.
- **Measured:** not yet run on GitHub (the repository is not pushed yet).
