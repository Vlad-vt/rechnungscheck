# ADR 0004: Synthetic dataset, independent oracle, reproducible rendering

- Status: accepted
- Date: 2026-11-23

## Context

Everything later in the project is measured against generated data: extraction accuracy, line matching, discrepancy detection, the correct-action rate and the safety gates. If the data or its labels are wrong, every number is wrong. The brief requires synthetic data, at least 200 cases split into dev and held-out test, every discrepancy type in the brief, injected instructions, and numbers reproducible from the repository.

## Decision

1. **A seeded generator** (`datagen/`) builds per-tenant master data, supplier contracts and purchase order → delivery note → invoice triples. Each case is a clean triple plus one mutation (a few get two). The result is 246 cases: 82 per tenant, 41 dev / 41 test, stratified by scenario.
2. **Ground truth is the canonical `Invoice`** (ADR 0002) as printed or encoded in the document, plus typed discrepancy labels carrying line, field, tolerance flag and monetary impact.
3. **An independent oracle** (`datagen/labels.py`) derives the expected decision (`requires_human`, action) from the labels and the tenant config with a short, table-like rule list. It shares no code with the product's policy gate, so the product is evaluated against a separate implementation, not against itself.
4. **Identifiers come from ranges that do not belong to anyone:**
   - GTINs use the GS1 restricted-circulation prefix 2xx.
   - IBANs use bank code 99xxxxxx, with a valid mod-97 check.
   - VAT ids are `DE99…`, with a valid check digit.
   - Emails use the reserved `.example` TLD.
5. **Batch, best-before and serial numbers** travel in the line note (BT-127) in a fixed format. EN 16931 has no business terms for them, so this keeps the XML conformant to EN 16931 and to the Factur-X EN 16931 XSD. Parsers read the note back.
6. **Rendering is byte-reproducible on one platform:**
   - reportlab runs in invariant mode.
   - The sRGB ICC profile gets a fixed date and a zeroed id.
   - factur-x's clock is pinned to the invoice date.
   - Scans are PNG, not JPEG.

   SHA-256 hashes of all 483 documents are committed. `make data && make data-verify` checks them.
7. **What is committed:** master data, contracts and case manifests (small, reviewable). Rendered documents (about 9 MB) are regenerated, not committed.
8. **ZUGFeRD hybrids are PDF/A-3.** Fonts are embedded (Bitstream Vera, shipped with reportlab) and an sRGB OutputIntent is added. Mustang's veraPDF accepts them (ADR 0003).

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Hand-written cases | Too few for 200+ cases with coverage per tenant and per type. |
| LLM-generated invoices | Labels would not be trustworthy, generation is not reproducible, and it costs money. |
| Public corpus only | It has no purchase orders, delivery notes, tenant policies or discrepancy labels. It is used only for validator and extraction checks. |
| Expected decision from the product's policy code | Circular. A bug would be "confirmed" by the eval. |
| Structured batch/serial elements (CII `IndividualTradeProductInstance`, UBL `ItemInstance`) | Not part of EN 16931. The Factur-X EN 16931 XSD rejects them. |
| Faker for names | Uncontrolled real-sounding names and random real-looking identifiers. A small curated catalogue is enough. |

## Consequences

- Labels are only as good as the generator. Unit tests check the invariants:
  - every expected action is in the tenant's catalogue;
  - safety cases always need a human;
  - duplicates exist in the invoice history;
  - changed IBANs differ from master data;
  - the split is balanced per scenario.
- **Cross-platform bytes were measured, and an earlier claim was corrected.**
  - An earlier version of this ADR said all 483 documents were byte-identical between Windows and Linux. That was wrong: the CI step had compared regenerated files against a hash list the same generation had just rewritten.
  - The blocking check in CI run 45144149063 (commit 18c93e7) showed the real picture:
    - all 102 XML files are identical;
    - all 333 PDFs and 48 PNGs differ between a Windows host and a Linux runner, because the zlib, libpng and pdfium builds differ.
  - **Fix:** the canonical dataset is rendered in a digest-pinned container (`datagen/Dockerfile`, `make data`). Locally on Windows, two container runs produced identical bytes for all 535 tenant and document files.
  - CI regenerates in the same image and fails on any difference in manifests or document hashes. There are no exceptions per file type.
  - `make data-native` (host Python) is faster, but its PDF/PNG bytes are not canonical and must not be committed.
- The scenario name is the generator recipe. The labels are the truth. For example, a "within tolerance" recipe for a zero-tolerance tenant yields an out-of-tolerance label.
