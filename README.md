# Azure Migration Lab

Hands-on DevOps migration lab focused on migrating an application and PostgreSQL database to Microsoft Azure.

## Architecture

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