# Phase 0 preflight: RechnungsCheck

Date: 2026-11-22. Nothing was created: only read-only calls, ARM `validate` and `what-if`. Identifiers are redacted to their last four characters. The probe template is [`infra/bicep/preflight/`](../infra/bicep/preflight/). It is never deployed.

## TL;DR

- **Proposed mode: A (provisional).** No policy or offer restriction blocks Foundry, model deployments, managed identities, federated credentials, role assignments or budgets in `germanywestcentral`, and the model quotas are non-zero. One gap remains: ARM validation does **not** check model-deployment quota (proven by a negative control below), so only a real deployment can fully confirm Mode A. That test needs approval.
- **Region:** `germanywestcentral`. Every resource type the brief needs is offered there.
- **Credit:** USD 100 Azure for Students credit, unused, expires 2027-10-02. Spending limit is on.
- **Open before Phase 5:** 10 resource providers are not registered. Postgres Flexible Server and ACR Basic bill while idle, so they need your approval.

## Subscription and credit

| Item | Finding |
|---|---|
| Offer | Azure for Students (`quotaId` `AzureForStudents_2018-01-01`), subscription `…c8ca`, Enabled |
| Spending limit | On: resources are disabled when the credit is used up, nothing is billed to a card |
| Credit (billing profile, `Microsoft.Consumption/credits/balanceSummary`) | current balance **USD 100.00** of 100.00; lot "Azure for students credit", 2026-10-02 to **2027-10-02** |
| Other credit lot | expired 2023 sign-up credit, balance 0 (irrelevant) |
| Cost month to date | USD 0 |
| Billing agreement | Microsoft Customer Agreement |
| Existing budget | `monthly-10usd` (USD 10/month, subscription scope) |

## Identity and permissions

| Item | Finding |
|---|---|
| Signed-in principal | user in the subscription's home tenant (`…8144`) |
| RBAC | **Owner** on the subscription (+ Foundry User) |
| Entra | Global Administrator; `allowedToCreateApps: true` |
| User-assigned managed identity + GitHub federated credential | `validate` and `what-if` succeed |
| Role assignment (Cognitive Services OpenAI User to the identity) | `validate` and `what-if` succeed |
| Budget at subscription scope | supported: one exists, and the probe budget passes `what-if` |

The brief's choice of OIDC through a user-assigned managed identity with a federated credential works. An app registration would also be possible, but it is not needed.

## Policy and regions

One assignment, `sys.regionrestriction`: built-in "Allowed resource deployment regions", effect **deny**, mode `Indexed`. Resource groups are not covered because of the `Indexed` mode, and `global` resources are exempt.

Allowed: `germanywestcentral`, `switzerlandnorth`, `norwayeast`, `denmarkeast`, `belgiumcentral`.

Negative control: the same probe with `location=westeurope` fails `validate` with `RequestDisallowedByAzure` for every resource. So `validate` does evaluate the policy on resources inside the not-yet-existing resource group.

## Resource types in the allowed regions

| Resource type | Provider state | Allowed regions where offered |
|---|---|---|
| Microsoft.CognitiveServices/accounts | Registered | germanywestcentral, switzerlandnorth, norwayeast |
| Microsoft.ManagedIdentity (identities, federated credentials) | Registered | all 5 |
| Microsoft.Consumption/budgets | Registered | global |
| Microsoft.App (managedEnvironments, jobs) | **NotRegistered** | all except denmarkeast |
| Microsoft.DBforPostgreSQL/flexibleServers | **NotRegistered** | all 5 |
| Microsoft.Search/searchServices | **NotRegistered** | all 5 |
| Microsoft.Storage/storageAccounts | **NotRegistered** | all 5 |
| Microsoft.ServiceBus/namespaces | **NotRegistered** | all 5 |
| Microsoft.EventGrid/systemTopics | **NotRegistered** | all 5 |
| Microsoft.KeyVault/vaults | **NotRegistered** | all 5 |
| Microsoft.ContainerRegistry/registries | **NotRegistered** | all 5 |
| Microsoft.OperationalInsights/workspaces, Microsoft.Insights/components | **NotRegistered** | all 5 |

`germanywestcentral` is the only allowed region that offers everything, which makes it the choice. The region lists come from provider metadata, which is readable without registration. Registration is free, but it is a subscription change, so it was not done. Until it is, `what-if` was not run for these types, and the AI Search tier quota (whether the Free tier is available) and the Postgres SKU capabilities could not be read.

## Cognitive Services kinds (germanywestcentral)

`az cognitiveservices account list-skus`: no restrictions reported for

| Kind | SKUs |
|---|---|
| AIServices (Foundry) | S0 |
| FormRecognizer (Document Intelligence) | F0, S0 |
| ContentSafety | F0, S0 |
| OpenAI | S0 |
| TextAnalytics (Language, PII detection) | F0, S |

`ContentUnderstanding` is not a separate kind. Content Understanding runs inside an AIServices (Foundry) resource, and its region availability is to be checked against the docs before Phase 4. Region availability of Prompt Shields is also to be checked against the docs.

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

**Vision:** the catalogue has no `vision` capability flag, so image input has to be confirmed by a test call. The Phase 0 rules allow none without a deployment.

**Validation does not check quota.** Negative control: the probe with the small-model deployment at capacity 900000 (far above the 1000 limit) still **passes** `validate`. A passing `validate` is therefore no evidence that a deployment will be accepted. Quota evidence comes from `az cognitiveservices usage list` only.

## Public list prices relevant to idle cost (germanywestcentral)

Source: Azure Retail Prices API, 2026-11-22, list prices before credit.

| Item | Price | Bills while idle? |
|---|---|---|
| PostgreSQL Flexible Server Burstable B1ms compute | USD 0.0199 / hour | yes while running; storage also while stopped; a stopped server restarts automatically after 7 days |
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

`rg-ai-lab` (polandcentral) holds one AIServices account in germanywestcentral and one Foundry project, with no deployments. It will not be touched. Project resources go into `rg-rechnungscheck-dev`, tagged `project=rechnungscheck`.

## What still needs a real action (approval required)

1. **Register resource providers** (free): App, DBforPostgreSQL, Search, Storage, ServiceBus, EventGrid, KeyVault, ContainerRegistry, OperationalInsights, Insights. This unblocks `what-if` for the rest of the stack and the AI Search Free-tier and Postgres SKU checks.
2. **One real model test**: a temporary resource group with one AIServices account and small GlobalStandard deployments of the small, strong and embedding candidates. One tiny call each, including one image input, then the resource group is deleted. The deployments do not bill while idle; the cost is token usage only.
3. **Budget ceiling** for the project.

## Brief items that need a decision later

- **Postgres Flexible Server** bills while running (B1ms list price above) and partly while stopped, and it restarts by itself after 7 days. `make stop` limits but does not remove the idle cost. Decide in Phase 5. Whether the student offer includes free B1ms hours has to be checked, not assumed.
- **ACR Basic** bills every day. The alternative is GHCR with public images, which Container Apps can pull without credentials. Decide in Phase 5.
- **AI Search Free** is listed for the region. Availability for this subscription (one Free service per subscription) can be checked after provider registration. pgvector stays the fallback.

## Reproduce

```bash
az account show
az rest --method get --url "https://management.azure.com/subscriptions/<sub>?api-version=2022-12-01"
az rest --method get --url "https://management.azure.com/providers/Microsoft.Billing/billingAccounts/<ba>/billingProfiles/<bp>/providers/Microsoft.Consumption/credits/balanceSummary?api-version=2023-05-01"
az role assignment list --assignee <me> --all
az policy assignment list --disable-scope-strict-match
az policy definition show --name b86dabb9-b578-4d7b-b842-3b45e95769a1
az rest --method get --url "https://graph.microsoft.com/v1.0/policies/authorizationPolicy"
az provider list ; az provider show -n <namespace>     # registration state and per-type locations
az cognitiveservices account list-skus --kind <kind> --location germanywestcentral
az cognitiveservices model list -l germanywestcentral
az cognitiveservices usage list -l germanywestcentral
az deployment sub validate -l germanywestcentral -f infra/bicep/preflight/preflight.bicep
az deployment sub validate -l germanywestcentral -f infra/bicep/preflight/preflight.bicep -p location=westeurope   # expect RequestDisallowedByAzure
az deployment sub what-if  -l germanywestcentral -f infra/bicep/preflight/preflight.bicep
curl -G https://prices.azure.com/api/retail/prices --data-urlencode "$filter=armRegionName eq 'germanywestcentral' and serviceName eq '<service>'"
```
