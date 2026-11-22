// Phase 0 validate-only probe (never deployed): platform services in germanywestcentral.
param location string = 'germanywestcentral'
var s = uniqueString(resourceGroup().id)
resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-rc-${s}'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30, workspaceCapping: { dailyQuotaGb: 1 } }
}
resource env 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-rc-${s}'
  location: location
  properties: { workloadProfiles: [ { name: 'Consumption', workloadProfileType: 'Consumption' } ] }
}
resource sb 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: 'sb-rc-${s}'
  location: location
  sku: { name: 'Basic', tier: 'Basic' }
  properties: { disableLocalAuth: true }
}
resource st 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: 'strc${s}'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: { allowSharedKeyAccess: false, minimumTlsVersion: 'TLS1_2' }
}
resource kv 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: 'kv-rc-${s}'
  location: location
  properties: { tenantId: subscription().tenantId, sku: { family: 'A', name: 'standard' }, enableRbacAuthorization: true }
}
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acrrc${s}'
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}
