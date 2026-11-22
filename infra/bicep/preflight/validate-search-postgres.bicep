// Phase 0 validate-only probe (never deployed): AI Search Free and Postgres B1ms.
param location string = 'germanywestcentral'
var s = uniqueString(resourceGroup().id)
resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: 'srch-rc-${s}'
  location: location
  sku: { name: 'free' }
  properties: { replicaCount: 1, partitionCount: 1 }
}
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: 'psql-rc-${s}'
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '17'
    storage: { storageSizeGB: 32 }
    authConfig: { activeDirectoryAuth: 'Enabled', passwordAuth: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
  }
}
