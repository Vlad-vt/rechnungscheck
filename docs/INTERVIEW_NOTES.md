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

## Synthetic data generator (datagen/, ADR 0004)

- **What:** a seeded generator. Per tenant it builds master data, framework contracts and labelled purchase order → delivery note → invoice cases.
  - 246 cases in total (82 per tenant, 41 dev / 41 test).
  - 19 scenario recipes covering every discrepancy type in the brief.
  - Injected instructions, visible and hidden, in about 12 % of cases.
- **Formats:** XRechnung CII and UBL, ZUGFeRD PDF/A-3 hybrids, text PDFs and scan-like PNGs, plus delivery note PDFs.
- **Why it matters:** every later number is measured against these labels. The expected decision comes from an independent oracle (`datagen/labels.py`). It deliberately does not reuse product code, so a policy bug cannot "confirm itself".
- **Design points to explain:**
  - Identifiers come from ranges nobody owns: GTIN prefix 2xx, bank code 99, `DE99` VAT ids, `.example` emails.
  - Batch, best-before and serials travel in the EN 16931 line note, because EN 16931 has no business terms for them and this keeps the files EN 16931-conformant.
  - One shared supplier appears in all tenants with different IBANs and contract terms, as a cross-tenant leakage tripwire.
  - The seed lives in `tenants/<id>/datagen.yaml`, so a new demo tenant needs no code change.
- **Reproducibility:**
  - Output is byte-identical across runs: reportlab invariant mode, an ICC profile with a fixed date, factur-x's clock pinned to the invoice date, PNG instead of JPEG.
  - The SHA-256 of all 483 documents is committed.
  - Moving the seed from code to YAML was proven by a before/after SHA-256 comparison of all 535 tenant and document files.
- **Lessons:**
  - The first ZUGFeRD files were not PDF/A-3. Mustang's veraPDF showed two causes: fonts not embedded, and DeviceGray without an OutputIntent. Both were fixed.
  - Two non-determinism sources (the ICC timestamp and factur-x's `datetime.now()`) were found by diffing bytes from two processes.

## Format router and structured parsers (src/rechnungscheck/extraction)

- **What:**
  - The router (node 1, plain code) decides UBL vs CII by the XML root, ZUGFeRD by the embedded `factur-x.xml`, and text PDF vs scan by the length of the text layer.
  - The parsers map CII, UBL and ZUGFeRD into the canonical model. Every value carries an XPath evidence id.
- **Measured** (`tests/unit/test_extraction.py` and a full round-trip over the dataset):
  - all 246 generated documents were routed correctly;
  - all 168 structured invoices parse to exactly the ground truth (flattened field-by-field comparison).
- **Robustness:** values that fail type validation (a unit code "piece", a decimal comma) are dropped and recorded as warnings instead of crashing. The Compliance Checker then sees a missing field.
- **Security:** XML is parsed with DTDs, entities and network access disabled, and any DOCTYPE is rejected. Tests cover XXE, entity expansion and an external DTD.

## Validator: KoSIT service, Mustang offline (ADR 0003)

- **Measured** on 389 files: 221 from the ZUGFeRD corpus and 168 generated. Run on commit `8bd6ee6`, results in `evals/results/validator_comparison/latest.md`.
  - **Agreement on generated files:** KoSIT 168/168, Mustang 167/168. The one difference is a line arithmetic error that Mustang flags via PEPPOL-EN16931-R120 and KoSIT's official XRechnung 3.0.2 configuration does not.
  - **Coverage:** KoSIT can judge only 121 of the 221 corpus files (no ZUGFeRD 1, no Factur-X BASIC / EXTENDED). Mustang judges all of them and also checks PDF/A-3.
  - **Speed:** KoSIT median 6–31 ms per file as a daemon. Mustang median 4.7–15.2 s per CLI call.
- **Decision:** KoSIT as the internal service, Mustang offline (PDF/A checks of generated data, second opinion).
- **Key interview point:** validators catch format and EN 16931 rule errors, not business errors. Short delivery, price deviation, wrong VAT for the product, changed IBAN and duplicates passed both validators every time. That is exactly why matching, the investigator and the policy gate exist.
- **Design detail:** "no scenario matched" is reported as `unsupported`, not invalid. The case then relies on the product's own checks and goes to review.
