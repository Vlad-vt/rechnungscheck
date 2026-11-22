# ADR 0001: Postgres in belgiumcentral, everything else in germanywestcentral

- Status: accepted
- Date: 2026-11-22

## Context

The Azure for Students subscription may only deploy to `germanywestcentral`, `switzerlandnorth`, `norwayeast`, `denmarkeast` and `belgiumcentral`. This is enforced by an Azure Policy deny.

Two facts from the Phase 0 preflight ([PREFLIGHT.md](../PREFLIGHT.md)) shape the choice:

- Foundry (Cognitive Services) accounts are offered only in `germanywestcentral`, `switzerlandnorth` and `norwayeast`. A real smoke test in `germanywestcentral` confirmed model deployment, image input, Document Intelligence and Prompt Shields.
- `az postgres flexible-server list-skus -l germanywestcentral` reports "Provisioning is restricted in this region" for this subscription. The other four allowed regions offer Burstable B1ms and PostgreSQL 16 to 18. ARM `validate` does not catch this restriction.

EU data residency matters for invoice data.

## Decision

Deploy PostgreSQL Flexible Server in `belgiumcentral`, which is in the EU. Deploy every other resource in `germanywestcentral`: Foundry, Container Apps, Service Bus, Storage, Event Grid, Key Vault, AI Search, the registry and monitoring.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Everything in `switzerlandnorth` or `norwayeast` (single region) | Simpler, but the data leaves the EU: Switzerland has an EU adequacy decision, Norway is EEA |
| Postgres in `denmarkeast` | Also EU and equally valid. Container Apps is not offered there, so no future co-location of compute and database is possible |
| Self-managed Postgres in a container | More to operate (backups, persistence, Entra auth); weaker as a portfolio story |
| Support request for a germanywestcentral exception | Outcome and timing unknown; can be revisited later |

## Consequences

- Every database round trip crosses regions. Inter-region latency and egress cost have **not been measured yet**. They will be measured in Phase 5 (p50/p95 query latency from a Container App in `germanywestcentral`) and recorded here.
- Bicep needs a separate `location` parameter for the database module.
- The LangGraph checkpointer writes once per graph step, so per-step latency adds up. If the measurement shows a material effect, revisit this ADR.
