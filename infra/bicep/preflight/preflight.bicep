// Phase 0 preflight probe. Used ONLY with `az deployment sub validate` and
// `az deployment sub what-if`; it is never deployed. It checks that the
// subscription's policies, offer and quotas would accept the resource types
// whose providers are already registered (Cognitive Services, Managed
// Identity, Consumption budgets).
targetScope = 'subscription'

@description('Region to probe. Must be in the subscription allow-list to pass.')
param location string = 'germanywestcentral'

@description('Monthly budget amount in USD (probe value only).')
param budgetAmount int = 20

@description('First day of the current month, required by budgets.')
param budgetStartDate string = '2026-11-01'

@description('GitHub repository used for the OIDC federated credential subject.')
param githubRepo string = 'example-owner/rechnungscheck'

var tags = {
  project: 'rechnungscheck'
  purpose: 'preflight-probe'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-rechnungscheck-preflight'
  location: location
  tags: tags
}

module probe 'probe-rg.bicep' = {
  name: 'preflight-probe'
  scope: rg
  params: {
    location: location
    tags: tags
    githubRepo: githubRepo
  }
}

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'rechnungscheck-preflight-budget'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      actual80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        thresholdType: 'Actual'
        contactRoles: [
          'Owner'
        ]
      }
    }
  }
}
