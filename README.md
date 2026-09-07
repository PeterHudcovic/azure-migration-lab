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
```

## Scheduled Cost Optimization

The AKS lab runs on a daily schedule to reduce unnecessary cloud cost.

- Cluster start: 07:45 Europe/Prague
- Public availability: approximately 08:00–20:00 Europe/Prague
- Cluster stop: 20:00 Europe/Prague

Azure Automation uses Managed Identity and RBAC to start and stop the AKS cluster without storing credentials.