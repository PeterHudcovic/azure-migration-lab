# Azure Migration Lab

Praktický DevOps migračný lab zameraný na migráciu aplikácie a PostgreSQL databázy do Microsoft Azure.

## Architektúra

```text
SOURCE / OLD ENVIRONMENT
Docker / local Kubernetes
  ├── Web/API
  └── PostgreSQL
        │
        │ migration
        ↓
AZURE
Terraform
  ├── Resource Group
  ├── VNet
  ├── Subnet
  ├── AKS
  ├── ACR
  ├── Key Vault
  └── Terraform Remote State

GitHub
   │
   ├── GitHub Actions
   │
   └── Jenkins
          │
          ↓
Docker Build
          │
          ↓
ACR
          │
          ↓
Helm
          │
          ↓
AKS
  ├── migration-app Deployment
  └── PostgreSQL StatefulSet + PVC