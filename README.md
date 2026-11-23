# RechnungsCheck

Multi-tenant agents that check incoming German e-invoices (ZUGFeRD / Factur-X, XRechnung, PDFs, scans) for compliance, reconcile them line by line against purchase orders and delivery notes, investigate discrepancies and either auto-approve within each client's policy or prepare a case for a human reviewer.

**Status:** under construction (Phase 2 of 8: synthetic data, parsers, validator). There are no results yet. Every number this README will report comes from committed eval runs on synthetic data.

All data in this repository is synthetic.

## Quick start (development)

```bash
make install
make check
uv run rechnungscheck tenants validate
```

See [`docs/PREFLIGHT.md`](docs/PREFLIGHT.md) for the Azure subscription findings and [`docs/adr/`](docs/adr/) for decisions.
