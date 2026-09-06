terraform {
  backend "azurerm" {
    resource_group_name  = "rg-migration-lab"
    storage_account_name = "stmigrationlabtfstate"
    container_name       = "tfstate"
    key                  = "migration-lab.tfstate"
  }
}