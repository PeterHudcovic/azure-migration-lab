resource "azurerm_resource_group" "main" {
  name     = "rg-migration-lab"
  location = "westeurope"
}

resource "azurerm_virtual_network" "main" {
  name                = "vnet-migration-lab"
  address_space       = ["10.10.0.0/16"]
  location            = "swedencentral"
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_subnet" "aks" {
  name                 = "snet-aks"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.10.1.0/24"]
}

resource "azurerm_container_registry" "main" {
  name                = "acrmigrationlab"
  resource_group_name = azurerm_resource_group.main.name
  location            = "northeurope"
  sku                 = "Basic"
  admin_enabled       = false
}

resource "azurerm_kubernetes_cluster" "main" {
  name                = "aks-migration-lab"
  location            = "swedencentral"
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = "aks-migration-lab"

  kubernetes_version = "1.36.3"
  sku_tier           = "Free"

  default_node_pool {
    name           = "system"
    node_count     = 1
    vm_size        = "Standard_B2s_v2"
    vnet_subnet_id = azurerm_subnet.aks.id
  }

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
}