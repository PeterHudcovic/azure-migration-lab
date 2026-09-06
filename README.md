# Azure Migration Lab

Practical DevOps migration lab demonstrating migration of an application and PostgreSQL workload to Microsoft Azure.

## Architecture

```text
Source / Legacy Environment
        |
        | Migration
        v
Microsoft Azure
|
+-- Terraform
|   +-- Resource Group
|   +-- Virtual Network
|   +-- Subnet
|   +-- Azure Kubernetes Service
|   +-- Azure Container Registry
|   +-- Azure Key Vault
|   +-- Remote Terraform State
|
+-- Azure Kubernetes Service
    +-- Application Deployment
    +-- PostgreSQL StatefulSet
    +-- Persistent Volume Claim
    +-- Service
    +-- Ingress
```

## CI/CD

Two CI/CD (Continuous Integration / Continuous Delivery) implementations are included.

### GitHub Actions

```text
Git Push
   |
   v
GitHub Actions
   |
   +-- Build Docker image
   +-- Login to Azure
   +-- Push image to ACR
   +-- Get AKS credentials
   +-- Helm deployment
   v
AKS
```

Workflow:

`.github/workflows/deploy.yml`

### Jenkins

```text
GitHub
   |
   v
Jenkins
   |
   +-- Docker Build
   +-- Azure Login
   +-- Push to ACR
   +-- Helm Upgrade
   +-- Kubernetes Verification
   v
AKS
```

Pipeline:

`Jenkinsfile`

Custom Jenkins runtime:

`Dockerfile.jenkins`

## Infrastructure as Code

Terraform is used for IaC (Infrastructure as Code).

Directory:

`terraform/`

Resources include:

- Azure Resource Group
- VNet (Virtual Network)
- Subnet
- AKS (Azure Kubernetes Service)
- ACR (Azure Container Registry)
- Azure Key Vault
- ACR Pull RBAC (Role-Based Access Control)
- Terraform remote state configuration

## Kubernetes and Helm

The application is deployed using Helm.

Directory:

`helm/migration-app/`

The Helm Chart manages:

- Application Deployment
- Kubernetes Service
- PostgreSQL StatefulSet
- PVC (Persistent Volume Claim)
- Kubernetes Secret
- Ingress
- Health probes

Environment-specific values:

- `values-dev.yaml`
- `values-test.yaml`
- `values-prod.yaml`

## PostgreSQL

PostgreSQL 16 runs as a Kubernetes StatefulSet with persistent storage.

Migration procedure:

`migration/README.md`

Migration scripts:

- `migration/backup-postgres.sh`
- `migration/restore-postgres.sh`

Migration flow:

```text
Source PostgreSQL
       |
       | pg_dump
       v
Backup
       |
       | pg_restore
       v
Target PostgreSQL
       |
       v
Application validation
       |
       v
Cutover
```

## Ansible

Ansible is included for configuration automation.

Directory:

`ansible/`

Files:

- `inventory.ini`
- `playbook.yml`

## Secrets

Secrets are not stored directly in source code.

The project demonstrates:

- Jenkins Credentials
- GitHub Actions Secrets
- Kubernetes Secrets
- Azure Key Vault configuration

## Rollback

Rollback procedures are documented in:

`docs/rollback.md`

Supported rollback methods include:

- Helm rollback
- Kubernetes Deployment rollback
- PostgreSQL migration rollback

## Troubleshooting

Troubleshooting runbook:

`docs/troubleshooting.md`

The runbook covers:

- Pod failures
- Deployment failures
- Image pull failures
- Application connectivity
- PostgreSQL connectivity
- Helm deployment failures

## Technology Stack

- Microsoft Azure
- AKS (Azure Kubernetes Service)
- ACR (Azure Container Registry)
- Terraform
- Kubernetes
- Helm
- Docker
- Jenkins
- GitHub Actions
- Ansible
- PostgreSQL
- Python / Flask
- Git

## Repository Structure

```text
azure-migration-lab/
|
+-- .github/workflows/
+-- ansible/
+-- app/
+-- docs/
+-- helm/
+-- k8s/
+-- migration/
+-- terraform/
+-- Dockerfile.jenkins
+-- Jenkinsfile
+-- README.md
```