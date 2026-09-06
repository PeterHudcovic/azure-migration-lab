data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "migration" {
  name                = "kv-migration-lab"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  enable_rbac_authorization = true
}