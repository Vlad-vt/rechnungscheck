# ADR 0003: KoSIT as the runtime validator, Mustang offline for PDF/A

- Status: accepted
- Date: 2026-11-23
- Measurement: `evals/results/validator_comparison/latest.{json,md}`
  - repo commit `8bd6ee6` (clean tree)
  - ZUGFeRD corpus commit `02d4b56`
  - reproduce with `make up corpus data docker-build compare-validators`

## Context

The Compliance Checker needs an EN 16931 / XRechnung validator running as an internal container. The brief names two open-source candidates, both Apache-2.0:

- **KoSIT validator** 1.6.3 with the official XRechnung 3.0.2 configuration (2026-08-31). It checks XML only and runs as an HTTP daemon.
- **Mustang** 2.26.0 CLI. It checks ZUGFeRD 1/2, Factur-X profiles, XRechnung CII and UBL, and PDF/A-3 through veraPDF. It is CLI only; the REST server is a separate commercial product.

## Measurement

389 files in total:

| Source | Files | Expected verdict |
|---|---|---|
| Public ZUGFeRD corpus | 221 | invalid if the file is in a `fail/` directory, valid otherwise |
| Generated XRechnung CII, XRechnung UBL and ZUGFeRD files | 168 | from the labels (invalid only for BR-CO-15 total errors, and for BR-DE-15 on XRechnung) |

### Results

| | KoSIT | Mustang |
|---|---|---|
| Generated files: agreement with expectation | **168 / 168** | **167 / 168** |
| Generated ZUGFeRD PDF/A-3 (veraPDF) | not checked | 66 / 66 pass |
| Corpus files it could judge at all | 121 / 221 | 221 / 221 |
| ZUGFeRD v2 `fail/`: false accepts | 3 of 12 judged | 7 of 24 (own summary); 6 of 24 with PDF/A errors counted |
| Corpus "correct" files rejected | 14 of 109 judged | 33 of 194 |
| Median time per file | 6–31 ms (HTTP to running daemon) | 4.7–15.2 s (CLI incl. JVM start, 8 in parallel on 16 CPUs) |
| Files judged by both: same verdict | 273 / 289 | |

### Notes on the numbers

- **Where KoSIT cannot judge a file**, no scenario of the XRechnung configuration matches it. This covers ZUGFeRD 1, Factur-X BASIC / EXTENDED, older XRechnung versions and PEPPOL BIS. The client reports these as `unsupported`, not as invalid. One corpus file with a broken XML encoding attribute got HTTP 422 (processing error).
- **The single generated disagreement** is a UBL invoice with a wrong line net amount. Mustang's bundled XRechnung UBL stylesheet flags it under PEPPOL-EN16931-R120. KoSIT with the official 3.0.2 configuration does not. Across all seven line-arithmetic cases KoSIT caught 0 and Mustang caught 1. Neither validator catches any business discrepancy: short delivery, price deviation, wrong VAT rate for the product, changed IBAN, duplicates, shelf life.
- **The corpus labels come from directory names.** The disagreements on corpus "correct" files were not inspected one by one. Some of those samples predate current rule versions. The rejection counts are therefore a comparison between the two validators, not proof that either one is wrong.

## Decision

**KoSIT runs as the internal validator service.** Mustang is **not deployed**. It is used offline, in the dataset pipeline and in the evals, as the PDF/A-3 check and as a second opinion.

Reasons:

1. **Latency and operating model.** KoSIT is a long-running HTTP daemon answering in milliseconds. Mustang is a CLI that pays a JVM start per call, so it would need a custom wrapper.
2. **Authority.** The KoSIT XRechnung configuration is the official reference for XRechnung, and its version is pinned explicitly.
3. **Honest verdicts.** KoSIT separates "no matching scenario" from "invalid". The product can treat the first as missing evidence, not as a defect.
4. Both validators agree on the generated data (168/168 vs 167/168). There is no accuracy reason to accept Mustang's runtime cost.

## Consequences

- **The Compliance Checker computes arithmetic itself**, including line net = quantity × price / base quantity, because neither validator covers it reliably. Business discrepancies stay with matching and the investigator anyway.
- **Profiles KoSIT does not cover** (ZUGFeRD 1, Factur-X BASIC / EXTENDED) get "validator: unsupported". The case relies on the product's own EN 16931 core checks and is flagged for review. It is not auto-rejected.
- **PDF/A conformance of incoming hybrids is not checked at runtime.** For accounts payable the XML is the legally relevant part. This limitation is documented.
- **Ops:** the validator container has no authentication. It must stay internal (no ingress) in Azure. Cold-start time with scale-to-zero is to be measured in Phase 5.
- **Pinning:** both images pin their downloads by SHA-256. Upgrading means changing the pin and re-running this comparison.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Mustang as the service (custom HTTP wrapper around the library) | Seconds per call and a custom Java wrapper to maintain, for 1 extra detection out of 168 generated files. |
| Both validators at runtime | Doubles cost and latency. Conflicting verdicts would still need a policy. |
| Hosted validation APIs | Third-party data transfer of invoices; ongoing cost; not reproducible offline. |
| Python-only (factur-x XSD + saxonche schematron) | Re-implements what KoSIT already ships as the official configuration. XRechnung schematron needs XSLT 2. |
