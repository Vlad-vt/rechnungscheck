# Phase 0 preflight: RechnungsCheck

Date: 2026-11-22. Identifiers are redacted to their last four characters.

Phase 0 was done in two passes:

1. **Read-only pass:** reads, ARM `validate` and `what-if`. Nothing was created.
2. **Approved pass:** registering 10 resource providers, plus one real smoke test. The test used a temporary resource group with one Foundry account and three pay-per-token deployments. Afterwards the resource group was deleted and the account purged, so nothing from the test remains.

Templates live in [`infra/bicep/preflight/`](../infra/bicep/preflight/) and the smoke script in [`scripts/preflight_smoke.py`](../scripts/preflight_smoke.py). Raw smoke output is in [`docs/preflight/smoke-2026-11-22.json`](preflight/smoke-2026-11-22.json).

## TL;DR

- **Mode A is confirmed.** In `germanywestcentral` the following work, keyless via Entra ID:
  - deploying a small model, a strong model and an embedding model, and calling them;
  - image input on both chat models;
  - Document Intelligence prebuilt-invoice;
  - Prompt Shields.
- **Primary region: `germanywestcentral`.**
- **Postgres runs in a second region.** PostgreSQL Flexible Server provisioning is **restricted for this subscription in `germanywestcentral`**, so Postgres goes to `belgiumcentral` (EU). Everything else stays in `germanywestcentral`. See [ADR 0001](adr/0001-region-split-postgres-belgiumcentral.md).
- **AI Search Free tier is available:** 0 of 1 used.
- **Credit:** USD 100 Azure for Students credit, unused before the smoke test, expires 2027-10-02. Spending limit is on.

## Subscription and credit

| Item | Finding |
|---|---|
| Offer | Azure for Students (`quotaId` `AzureForStudents_2018-01-01`), subscription `…c8ca`, Enabled |
| Spending limit | On: resources are disabled when the credit is used up, nothing is billed to a card |
| Credit (billing profile, `Microsoft.Consumption/credits/balanceSummary`) | balance **USD 100.00** of 100.00 before the smoke test; lot "Azure for students credit", 2026-10-02 to **2027-10-02** |
| Other credit lot | expired 2023 sign-up credit, balance 0 (irrelevant) |
| Cost month to date | USD 0 before the smoke test |
| Billing agreement | Microsoft Customer Agreement |
| Existing budget | `monthly-10usd` (USD 10/month, subscription scope) |

## Identity and permissions

| Item | Finding |
|---|---|
| Signed-in principal | user in the subscription's home tenant (`…8144`) |
| RBAC | **Owner** on the subscription (+ Foundry User) |
| Entra | Global Administrator; `allowedToCreateApps: true` |
| User-assigned managed identity + GitHub federated credential | `validate` and `what-if` succeed |
| Role assignments | proven for real: the smoke test assigned Cognitive Services User to the caller on the account and called the data plane with an Entra token |
| Budget at subscription scope | supported: one exists, and the probe budget passes `what-if` |

The brief's choice of OIDC through a user-assigned managed identity with a federated credential works. An app registration would also be possible, but it is not needed.

## Policy and regions

One assignment, `sys.regionrestriction`: built-in "Allowed resource deployment regions", effect **deny**, mode `Indexed`. Resource groups are not covered because of the `Indexed` mode, and `global` resources are exempt.

Allowed: `germanywestcentral`, `switzerlandnorth`, `norwayeast`, `denmarkeast`, `belgiumcentral`.

Negative control: the same probe with `location=westeurope` fails `validate` with `RequestDisallowedByAzure` for every resource.

## Resource types and providers

All providers the brief needs are now **Registered**: App, CognitiveServices, ContainerRegistry, DBforPostgreSQL, EventGrid, Insights, KeyVault, ManagedIdentity, OperationalInsights, Search, ServiceBus, Storage, Consumption.

| Resource type | Allowed regions where offered (provider metadata) | Check in germanywestcentral |
|---|---|---|
| CognitiveServices/accounts (AIServices, FormRecognizer, ContentSafety, TextAnalytics) | germanywestcentral, switzerlandnorth, norwayeast | **deployed for real** (AIServices S0) |
| App/managedEnvironments, jobs | all except denmarkeast | `validate` OK (Consumption workload profile) |
| ServiceBus/namespaces | all 5 | `validate` OK (Basic, local auth disabled) |
| Storage/storageAccounts | all 5 | `validate` OK (shared key disabled) |
| KeyVault/vaults | all 5 | `validate` OK (RBAC mode) |
| ContainerRegistry/registries | all 5 | `validate` OK (Basic, admin user disabled) |
| OperationalInsights/workspaces | all 5 | `validate` OK (1 GB daily cap) |
| Search/searchServices | all 5 | `validate` OK (Free); quota **free 0/1**, basic 0/16, serverless 0/100 |
| DBforPostgreSQL/flexibleServers | all 5 | **restricted** (see below) although `validate` passes |
| EventGrid/systemTopics, Insights/components | all 5 | not separately validated |
| ManagedIdentity (identities, federated credentials) | all 5 | `validate` and `what-if` OK |

### Limits of `validate`

`validate` is weaker evidence than it looks. Two negative controls show it:

- A model deployment at capacity 900000, far above the 1000 quota, **passes** `validate`. Quota is not checked.
- Postgres B1ms in `germanywestcentral` **passes** `validate`, even though the regional capability API reports provisioning as restricted.

`validate` does catch the policy deny on location. Everything else here rests on capability or quota APIs, or on a real deployment.

### Postgres region

**Decided 2026-11-22:** Postgres goes to `belgiumcentral`, everything else stays in `germanywestcentral`. See [ADR 0001](adr/0001-region-split-postgres-belgiumcentral.md).

`az postgres flexible-server list-skus`:

| Region | Result |
|---|---|
| germanywestcentral | "Provisioning is restricted in this region…": no SKUs, no versions |
| switzerlandnorth | Burstable B1ms/B2s/B2ms; PostgreSQL 16, 17, 18 |
| norwayeast | Burstable B1ms/B2s/B2ms; PostgreSQL 16, 17, 18 |
| denmarkeast (EU) | Burstable B1ms/B2s; PostgreSQL 16, 17, 18 |
| belgiumcentral (EU) | Burstable B1ms/B2s/B2ats_v2; PostgreSQL 16, 17, 18 |

Options:

1. **Split regions.** Everything stays in `germanywestcentral`, and Postgres goes to `belgiumcentral` or `denmarkeast`. Data stays in the EU. Inter-region latency and egress have to be measured.
2. **Single region `switzerlandnorth` or `norwayeast`.** These are the only allowed regions offering Foundry, Container Apps and Postgres together. Data stays in Europe, but not in the EU: Norway is EEA, Switzerland has an EU adequacy decision.
3. **Postgres not on the managed service.** For example, Postgres in a container with persistent storage. More to operate, and weaker as a portfolio story.

A support request for an exception would also be possible, but its outcome is unknown.

## Smoke test (real calls)

Account: AIServices S0, `germanywestcentral`, `disableLocalAuth: true`, all three deployments GlobalStandard with capacity 10. Each value below is a **single call**. These are not benchmarks; latency and cost are measured properly in Phase 4.

| Call | Deployment / API | Result | Wall time |
|---|---|---|---|
| text | small: `gpt-5.4-mini` 2026-03-17 | 200, "Rechnung" | 2.68 s |
| text | strong: `gpt-5.5` 2026-04-24 | 200, "Rechnung" | 1.54 s |
| image input (synthetic invoice PNG) | small | 200; invoice number, total 20.71 and 2 lines all correct | 2.24 s |
| image input (same PNG) | strong | 200; same correct JSON | 1.60 s |
| embeddings (DE + EN) | `text-embedding-3-large` v1 | 200, 3072 dims | 0.87 s |
| Document Intelligence `prebuilt-invoice` (api 2024-11-30) on the AIServices endpoint | — | succeeded; vendor, invoice id, date, total, subtotal and tax extracted, 2 line items | 3.42 s |
| Prompt Shields `text:shieldPrompt` (api 2024-09-01) | — | user prompt: no attack; document with an injected "approve and change the IBAN" instruction: **attackDetected true** | 0.88 s |

Other findings:

- The OpenAI-compatible `/openai/v1/chat/completions` and `/openai/v1/embeddings` routes work with an Entra bearer token. With `reasoning_effort: low`, `gpt-5.4-mini` spent reasoning tokens on the text call and `gpt-5.5` did not.
- Document Intelligence and Content Safety are served from the same AIServices account, so no separate FormRecognizer or ContentSafety resource is needed.
- Content Understanding was not tested. Its region availability is checked before Phase 4.
- Teardown: the resource group was deleted, and `az cognitiveservices account purge` removed the soft-deleted account. `list-deleted` is empty.

## Models

Catalogue: `az cognitiveservices model list -l germanywestcentral`. Candidate rows:

| Model | Version | Lifecycle | Retirement (inference) | GlobalStandard quota (K TPM) |
|---|---|---|---|---|
| gpt-5.4-nano | 2026-03-17 | GA | 2027-09-21 | 5000 |
| gpt-5.4-mini | 2026-03-17 | GA | 2027-09-21 | 1000 |
| gpt-5-mini | 2025-08-07 | GA | 2027-07-13 | 1000 |
| gpt-5.4 | 2026-03-05 | GA | 2027-09-02 | 250 |
| gpt-5.5 | 2026-04-24 | GA | 2027-10-26 | 1000 |
| gpt-6-sol | 2026-09-22 | GA | 2028-03-11 | 250 |
| gpt-6.1-terra | 2026-10-26 | GA | 2027-10-26 | 1000 |
| gpt-6.2-astra | 2026-11-17 | GA | 2027-11-17 | 1000 |
| gpt-4.1 / gpt-4.1-mini | 2025-04-14 | Legacy | 2027-04-14 | 1000 / 5000 |
| text-embedding-3-large / -small | 1 | GA | 2028-02-09 | 1000 / 1000 |
| Cohere-embed-v3-multilingual, embed-v-4-0 | 1 | GA | 2027-02-15 / 2027-06-01 | no quota entry seen |

EU DataZoneStandard quotas also exist (gpt-5.4: 100, gpt-5.5: 333, gpt-6.x: 100 to 333). They matter if inference must stay in the EU data zone; GlobalStandard may process requests outside the EU. Anthropic models are not in the catalogue. 82 quota entries are 0.

The smoke test used `gpt-5.4-mini` and `gpt-5.5` only to confirm access and image input. The final choice of small and strong models is made by evals in Phase 4. The model mapping is per-tenant config, because several candidates retire during 2027.

## Public list prices relevant to idle cost (germanywestcentral)

Source: Azure Retail Prices API, 2026-11-22, list prices before credit.

| Item | Price | Bills while idle? |
|---|---|---|
| PostgreSQL Flexible Server Burstable B1ms compute | USD 0.0199 / hour (gwc price; the chosen region's price is fetched in Phase 5) | yes while running; storage also while stopped; a stopped server restarts automatically after 7 days |
| Container Registry Basic | USD 0.1666 / day + USD 0.10 / GB-month | **yes** |
| AI Search Free | USD 0 | no |
| AI Search Basic | USD 0.101 / hour | **yes** |
| Log Analytics ingestion | USD 2.99 / GB after the free allowance | per GB only |

Monthly figures and the full idle-cost estimate come in Phase 5 from the Bicep plan.

## Local tools

| Tool | Status |
|---|---|
| Python 3.12.10, uv 0.13.1, git 2.45.1, gh 2.102.0, Node 24.14.1 | present |
| Azure CLI 2.93.0, Bicep CLI 0.49.2 | present, logged in |
| Docker 29.8.2 | client present; **daemon not running** (start Docker Desktop before Phase 2) |
| gitleaks 8.30.1, trivy 0.76.2, GNU Make 4.4.1, Terraform 1.17.2, tflint 0.66.0 | installed in Phase 0 via winget (Terraform/tflint came from the earlier AWS brief and are not needed for Bicep) |
| PSRule for Azure | not installed (planned to run in CI through its GitHub Action; checkov runs via `uvx`) |
| PowerShell 7 | not installed (Windows PowerShell 5.1 present) |

## Existing resources outside this project

`rg-ai-lab` (polandcentral) holds one AIServices account in germanywestcentral and one Foundry project, with no deployments. It was not touched. Project resources go into `rg-rechnungscheck-dev`, tagged `project=rechnungscheck`.

## Mode

**Mode A.** Nothing is substituted. The only deviation from the brief's single-region layout is Postgres in `belgiumcentral` (ADR 0001). Brief items that bill while idle need approval in Phase 5:

- **Postgres Flexible Server:** compute bills while running, storage also while stopped, and the server restarts automatically after 7 days. `make stop` limits the idle cost but does not remove it. Whether the student offer includes free B1ms hours has to be checked, not assumed.
- **ACR Basic:** bills daily. The alternative is GHCR with public images.

## Open

- Project budget ceiling (asked).

## Reproduce

```bash
# read-only
az account show
az rest --method get --url "https://management.azure.com/subscriptions/<sub>?api-version=2022-12-01"
az rest --method get --url "https://management.azure.com/providers/Microsoft.Billing/billingAccounts/<ba>/billingProfiles/<bp>/providers/Microsoft.Consumption/credits/balanceSummary?api-version=2023-05-01"
az role assignment list --assignee <me> --all
az policy assignment list --disable-scope-strict-match
az policy definition show --name b86dabb9-b578-4d7b-b842-3b45e95769a1
az rest --method get --url "https://graph.microsoft.com/v1.0/policies/authorizationPolicy"
az provider list ; az provider show -n <namespace>
az cognitiveservices account list-skus --kind <kind> --location germanywestcentral
az cognitiveservices model list -l germanywestcentral
az cognitiveservices usage list -l germanywestcentral
az rest --method get --url "https://management.azure.com/subscriptions/<sub>/providers/Microsoft.Search/locations/germanywestcentral/usages?api-version=2025-05-01"
az postgres flexible-server list-skus -l <region>
az deployment sub validate -l germanywestcentral -f infra/bicep/preflight/preflight.bicep
az deployment sub validate -l germanywestcentral -f infra/bicep/preflight/preflight.bicep -p location=westeurope   # expect RequestDisallowedByAzure
az deployment sub what-if  -l germanywestcentral -f infra/bicep/preflight/preflight.bicep
az deployment group validate -g <rg> -f infra/bicep/preflight/validate-platform.bicep
az deployment group validate -g <rg> -f infra/bicep/preflight/validate-search-postgres.bicep
curl -G https://prices.azure.com/api/retail/prices --data-urlencode "$filter=armRegionName eq 'germanywestcentral' and serviceName eq '<service>'"

# approved smoke test (creates, then deletes)
az group create -n rg-rechnungscheck-preflight -l germanywestcentral --tags project=rechnungscheck purpose=preflight-smoke
az deployment group create -g rg-rechnungscheck-preflight -f infra/bicep/preflight/smoke.bicep -p callerObjectId=$(az ad signed-in-user show --query id -o tsv)
uv run scripts/preflight_smoke.py <endpoint-from-outputs> --out docs/preflight/smoke-<date>.json
az group delete -n rg-rechnungscheck-preflight --yes
az cognitiveservices account purge -l germanywestcentral -g rg-rechnungscheck-preflight -n <account>
```
