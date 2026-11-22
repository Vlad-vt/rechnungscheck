// Phase 0 model smoke test. Deployed into a temporary resource group,
// exercised by scripts/preflight_smoke.py, then the resource group is
// deleted and the account purged. Pay-per-token deployments only.
param location string = resourceGroup().location

@description('Object id of the user who runs the smoke calls (keyless access).')
param callerObjectId string

param smallModel object = {
  name: 'gpt-5.4-mini'
  version: '2026-03-17'
}
param strongModel object = {
  name: 'gpt-5.5'
  version: '2026-04-24'
}
param embedModel object = {
  name: 'text-embedding-3-large'
  version: '1'
}

var tags = {
  project: 'rechnungscheck'
  purpose: 'preflight-smoke'
}
var suffix = uniqueString(resourceGroup().id)
var deployments = [
  { name: 'small', model: smallModel }
  { name: 'strong', model: strongModel }
  { name: 'embed', model: embedModel }
]

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: 'ais-rc-smoke-${suffix}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'ais-rc-smoke-${suffix}'
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

@batchSize(1)
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for d in deployments: {
    parent: foundry
    name: d.name
    sku: {
      name: 'GlobalStandard'
      capacity: 10
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: d.model.name
        version: d.model.version
      }
    }
  }
]

// Cognitive Services User: data-plane access to all Foundry APIs
// (models, Document Intelligence, Content Safety) without keys.
resource cogUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, callerObjectId, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  scope: foundry
  properties: {
    principalId: callerObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

output endpoint string = foundry.properties.endpoint
output accountName string = foundry.name
