# ADR 0002: Canonical invoice model with per-field evidence

- Status: accepted
- Date: 2026-11-22

## Context

Invoices arrive in four shapes: ZUGFeRD/Factur-X hybrids, XRechnung (UBL or CII), text PDFs, and scans. They are read by three kinds of extractors: structured XML parsers, a vision LLM, and Azure's prebuilt invoice model. Compliance checks, line matching, the investigator, the fact checker and the evals all need one shape to work on.

Two requirements make that shape special:

- The Fact Checker must trace every figure in a decision or a supplier email back to evidence.
- The evals compare extractors field by field, so a value and its provenance have to stay together.

## Decision

`rechnungscheck.domain.Invoice` is a frozen Pydantic model covering a subset of EN 16931:

- **Every field is `Extracted[T] | None`.** An `Extracted` holds the value, a confidence in 0..1, and a tuple of `Evidence` items. Evidence types: XPath for XML, page/bbox for images and PDF text, master-data key, or `derived` with the ids of its inputs.
- **Fields are optional.** The model records what was extracted, not what is valid. Mandatory-field checks (EN 16931 and per tenant) belong to the Compliance Checker, so a degraded scan still produces a model, plus a list of violations.
- **No arithmetic in the model.** Totals are stored as found. Recomputation happens in the compliance code, so a model can carry an arithmetic error found in the source.
- **Business-term ids are in the schema.** Each field has its EN 16931 business-term id in `json_schema_extra["bt"]`. Batch, best-before date and serial numbers are marked `EXT`: they are not EN 16931 core terms, but ZUGFeRD EXTENDED and delivery notes carry them.
- **Money and quantities are `Decimal` and must be finite.** YAML and JSON numbers go through their string form.
- **Tenant references are checked.** `INVOICE_FIELD_PATHS` lists every addressable field (`lines[].batch_number`). Tenant `mandatory_fields` are validated against it, so a typo in a tenant config fails CI.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Use the CII or UBL XML tree as the internal model | It ties every component to one syntax. Scans and LLM output have no XML. There is no place for confidence or evidence. |
| Reuse a library model (e.g. `drafthorse` document classes) | Built for writing ZUGFeRD, not for partial extraction with provenance. It also couples the domain to one library's release cycle. |
| A flat model plus a separate evidence map keyed by field path | Values and evidence drift apart when lines are reordered or merged. Harder to validate. |
| All fields required, with a separate "partial" model | Two models to keep in sync. The "is it valid?" logic would leak into parsing. |

## Consequences

- The model is verbose: `invoice.totals.total_with_vat.value` instead of `invoice.total`. Helpers can be added when the call sites exist.
- The evals can score each extractor per field and per document kind on the same type.
- The Fact Checker can resolve evidence ids without knowing which extractor produced them.
- Purchase orders and delivery notes get their own models in Phase 2, with the same `Extracted`/`Evidence` building blocks where they are extracted from documents.
