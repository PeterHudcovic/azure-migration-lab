# Azure Migration Lab

Hands-on DevOps migration lab focused on migrating an application and PostgreSQL database to Microsoft Azure.

**Live Operations Console:** https://ops.peterhudcovic.tech/

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

## Environments

Three Helm releases of the same `migration-app` chart, one per namespace, driven by
separate values files (`values-dev.yaml`, `values-test.yaml`, `values-prod.yaml`):

- `migration-app-dev` — namespace `dev`
- `migration-app-test` — namespace `test`
- `migration-app-prod` — namespace `prod`, the live environment behind
  https://ops.peterhudcovic.tech/

## Security

- **Workload Identity / OIDC** — Pods authenticate to Azure as
  `ServiceAccount → Workload Identity → OIDC → Managed Identity → Azure Key Vault`.
  The PostgreSQL password is never stored in Git or as a plain Kubernetes Secret
  value; it is delivered by the Secrets Store CSI driver.
- **RBAC** — the Operations Console's ServiceAccount is bound to a
  namespace-scoped `Role` (pods/services/deployments/ingresses in `prod` only)
  and a cluster-scoped `ClusterRole` limited to reading Nodes. No wildcard verbs
  or resources anywhere.
- **Operations Console command interface** — a read-only, whitelisted
  kubectl-style command set; no shell, no `subprocess`, no `eval`/`exec`.

## Ingress / HTTPS

NGINX Ingress Controller routes `https://ops.peterhudcovic.tech/` to the
Operations Console and `/pong` to the Pong demo workload. cert-manager issues
and renews the TLS certificate (`ClusterIssuer` `letsencrypt-prod`, Let's
Encrypt production, HTTP-01) for the shared `ops-peterhudcovic-tech-tls`
secret. DNS is managed in Cloudflare. Declarative platform configuration for
both is versioned under `k8s/platform/`.

## PostgreSQL Migration

PostgreSQL runs as a StatefulSet with a PersistentVolumeClaim. Migration
tooling under `migration/` performs a `pg_dump` → `pg_restore` cutover
(`backup-postgres.sh` / `restore-postgres.sh`), documented end-to-end in
`migration/README.md`. Both a Helm rollback and a Kubernetes rollout rollback
have been tested and are documented in `docs/rollback.md`.

## CI/CD

- **GitHub Actions** (`.github/workflows/deploy.yml`) — builds the Docker
  image, pushes it to ACR, and runs `helm upgrade --install
  migration-app-prod` with `values-prod.yaml` against the `prod` namespace.
  Path-filtered to `app/**` and `helm/migration-app/**`.
- **Jenkins** (`Jenkinsfile`) — an alternate pipeline for the same
  production target, authenticating with a service principal instead of
  GitHub's OIDC login action.

## Operations Console

A FastAPI dashboard, live at https://ops.peterhudcovic.tech/, for operating
this cluster without raw `kubectl` access:

- guest / user / admin roles, enforced server-side via signed JWT claims
- a restricted, read-only kubectl-style command interface
- live Kubernetes pod events over Server-Sent Events
- controlled scaling and rolling restart of the Pong demo workload
- a 15-minute Demo Mode that triggers a real rolling redeployment
- a built-in Project Guide documenting the architecture, Helm, CI/CD,
  security model and troubleshooting flow for this repository

## Scheduled Cost Optimization

The AKS lab runs on a daily schedule to reduce unnecessary cloud cost.

- Cluster start: 07:45 Europe/Prague
- Public availability: approximately 08:00–20:00 Europe/Prague
- Cluster stop: 20:00 Europe/Prague

Azure Automation uses Managed Identity and RBAC to start and stop the AKS cluster without storing credentials.