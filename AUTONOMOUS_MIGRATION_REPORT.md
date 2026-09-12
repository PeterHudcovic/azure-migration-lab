# Autonomous Azure → GCP Migration Report

**Branch:** `gcp-exact-clone` (Azure `main` untouched throughout)
**Live URL:** http://34.78.141.61/ (no DNS, no TLS, no Cloudflare — plain HTTP over a public IP, exactly as scoped)
**Status:** HOTOVO — pipeline green, application verified end-to-end.

## What this is

A functional clone of `azure-migration-lab`'s AKS/PostgreSQL/FastAPI Operations Console stack, redeployed on Google Kubernetes Engine in a dedicated GCP project (`migration-lab-gcp-clone`). Same application code, same Docker images (rebuilt for Artifact Registry), same Helm chart (`helm/migration-app`, `helm/pong-app`) with GCP-specific value overlays, same CI/CD shape (build → scan → push → Helm deploy), same Kubernetes objects (Deployments, StatefulSet, Services, Ingress, RBAC) — only the cloud-specific plumbing underneath differs.

## Component mapping (Azure → GCP)

| Azure | GCP |
|---|---|
| AKS (`aks-migration-lab`) | GKE (`gke-migration-lab`, europe-west1-b, 1× e2-medium node) |
| Azure Container Registry | Artifact Registry (`europe-west1-docker.pkg.dev/migration-lab-gcp-clone/migration-lab`) |
| Azure Disk (Key Vault CSI) | Google Persistent Disk (`standard-rwo`, GKE default StorageClass) |
| Azure Workload Identity + Key Vault | Plain Kubernetes Secret, populated once from a Terraform-generated `random_password` (Secret Manager holds the canonical copy; see "Secrets" below for why no CSI mount is used) |
| Azure Load Balancer (via ingress-nginx) | Google Cloud Load Balancer (via the same ingress-nginx chart) |
| `AZURE_CREDENTIALS` service principal | `github-actions-deploy` GCP service account, `roles/artifactregistry.writer` + `roles/container.developer` only |

## Terraform (`terraform-gcp/`)

New, separate from `terraform/` (Azure). Applied with local state (throwaway experiment, no remote backend). Creates: VPC + subnet (with GKE pod/service secondary ranges), two firewall rules (internal traffic, GCLB health checks), the GKE cluster (Workload Identity enabled, `deletion_protection = false` so it's actually destroyable), the Artifact Registry repo, the `github-actions-deploy` service account and its two IAM bindings, and a Secret Manager secret holding a freshly-generated Postgres password (never copied from Azure).

## Key decisions and why

**RBAC bootstrap is separated from the CI/CD deploy identity.** The Operations Console's own `templates/operations-rbac.yaml` (Role/RoleBinding for pods/services/deployments in `prod`, ClusterRole/ClusterRoleBinding for reading Nodes) used to be gated by the same `operations.enabled` flag as the app's runtime env vars. On GKE, managing Kubernetes RBAC objects via a GCP-authenticated principal requires specific `container.*Roles.*` IAM permissions that only `roles/container.admin` grants — and giving the CI/CD service account cluster-admin-adjacent rights just to `helm upgrade` the application was explicitly out of scope. Fix: a new value, `operations.manageRbac` (default `true`, so Azure/dev/test are byte-for-byte unaffected), gates the RBAC template independently of `operations.enabled`. `values-gcp.yaml` sets `manageRbac: false`. The RBAC objects themselves were rendered once (`helm template ... --set operations.manageRbac=true`) and applied once via `kubectl apply` under my own project-owner identity — a genuine one-time administrative bootstrap, never touched by the regular CI pipeline again. They're also annotated `helm.sh/resource-policy: keep` so a future `helm upgrade` (which no longer renders them) doesn't try to delete them.

**`github-actions-deploy` never held `container.admin`.** It was briefly considered and reverted before the CI pipeline ever ran with it (checked via `gcloud projects get-iam-policy` at the end — only `artifactregistry.writer` and `container.developer` are bound). All cluster-scoped/RBAC bootstrap work in this migration was done under my own `peter.hudcovic@gmail.com` project-owner identity, never through the pipeline's service account.

**Secrets: Secret Manager + a plain Kubernetes Secret, not the Key Vault-CSI equivalent.** GKE's managed Secret Manager CSI addon isn't exposed by the Terraform google provider version available here (`addons_config.secret_manager_config` doesn't exist in the schema). Rather than hand-install the CSI driver and its GCP provider as an extra unmanaged add-on for a throwaway experiment, the Postgres password is generated once by Terraform (`random_password`), written to Secret Manager as the canonical/durable copy, and delivered to the cluster as a plain Kubernetes Secret (`migration-postgresql-secret`) that the existing chart's `secretKeyRef` pattern already expects unchanged.

**pong-app's ingress no longer carries a leftover Azure hostname/TLS rule.** The shared `helm/pong-app/templates/ingress.yaml` unconditionally hardcoded a second rule and a `tls:` block for `ops.peterhudcovic.tech`. Harmless in practice (GCP's DNS never points there — dead config, not a bug), but not appropriate for a clean clone. Parameterized as `ingress.azureHost` (default = the Azure hostname, so Azure's render is unchanged byte-for-byte), set to `""` in `values-gcp.yaml`.

## Incidents hit and fixed during this run

1. **`migration-app-prod` stuck 0/1 NotReady for ~29h** — the app pod started 1 minute *before* the Postgres pod (both had restarted around the same time), `db.connect()` ran once at startup, failed since Postgres wasn't up yet, and latched `_pool = None` permanently (the app has no DB reconnect-retry logic — same known architectural gap documented on the Azure side). Fix: deleted the one stuck pod; the Deployment recreated it against an already-healthy Postgres. No code change; this is an existing, previously-documented limitation, not something introduced by this migration.
2. **Stale local gcloud identity.** A GCP service-account key had been locally activated in an earlier session and left as the active `gcloud` account, and a separate GKE-auth-plugin token cache (`~/.kube/gke_gcloud_auth_plugin_cache`) kept serving that stale identity even after switching back. Cleared the cache and used a short-lived access token directly for the one-time admin bootstrap steps.
3. **Windows gcloud ADC permission error** (`Access is denied` writing `adc.json` under `%APPDATA%\gcloud\legacy_credentials\...`) blocked the normal `gke-gcloud-auth-plugin` path entirely for my own account on this machine. Worked around it by injecting a `gcloud auth print-access-token` value directly into the kubectl context instead of relying on the exec plugin.
4. **Trivy failed on newly-disclosed Debian OS package CVEs** (gzip, libpcre2, libsqlite3, several perl-base CVEs) — unrelated to this app's Python dependencies (already patched earlier on the Azure side; those fixes are inherited on this branch too) and unrelated to anything in this migration. All had upstream fixes available; the base image tag just hadn't been rebuilt recently enough to include them. Fixed by adding `apt-get update && apt-get upgrade -y` to `app/Dockerfile` so the build always picks up the day's Debian security patches.
5. **Helm tried to `delete` the bootstrapped RBAC objects** on the first post-fix deploy, because its release metadata still remembered owning them from an earlier revision. Fixed with the `helm.sh/resource-policy: keep` annotation (see above).
6. **`pong-app` Helm upgrade conflicted on `.spec.replicas`**, owned by field-manager `OpenAPI-Generator` — the Kubernetes Python client the Operations Console uses for its own scale/restart actions defaults to that generic field-manager name under server-side apply, which collided with Helm's own (also server-side-apply-by-default in this Helm version) upgrade. `--force` turned out to be incompatible with server-side apply in this Helm version ("cannot use server-side apply and force replace together"); the actual fix was `--server-side=false` for this one upgrade step, falling back to a traditional strategic-merge patch that doesn't do field-manager ownership checks.

## Verification performed

- `/`, `/pong`, `/healthz`, `/readyz` all return 200 / `{"ok":true}` over `http://34.78.141.61/`.
- Guest login (`POST /api/login`) succeeds and issues a working JWT.
- All Pods `1/1 Running`, `0` restarts at time of report: `migration-app-prod`, `migration-postgresql-0`, `pong-app`.
- Deployments/StatefulSet: `migration-app-prod 1/1`, `pong-app 1/1`, `migration-postgresql 1/1`.
- Services have correct, non-empty Endpoints for all three workloads.
- Ingress: `migration-app-prod` (host-less `*`, path `/`) and `pong-app` (host-less, path `/pong(/|$)(.*)`) both resolve to the same GCLB external IP `34.78.141.61`; no Azure hostname remains in either.
- PVC `postgres-data-migration-postgresql-0` is `Bound`, `5Gi`, `RWO` — same StatefulSet+PVC design as Azure; the Postgres pod was never restarted during this entire session (30h+ uptime throughout), so no data-loss scenario was exercised or needed.
- GitHub Actions (`deploy-gcp.yml`) is green end-to-end: build → Trivy scan (0 CRITICAL/HIGH) → push both images → `helm upgrade` for both releases → rollout verification.
- IAM: `github-actions-deploy` holds exactly `roles/artifactregistry.writer` and `roles/container.developer` — confirmed via `gcloud projects get-iam-policy` after the final deploy, no `container.admin` anywhere.
- Git: no JSON key, no private key material, no plaintext secret anywhere in `gcp-exact-clone`'s commit history (checked via `git log -p` grep across the full branch diff against `main`). The one local SA key file (`terraform-gcp/.secrets/gha-deploy-key.json`, used only to seed the `GCP_CREDENTIALS` GitHub secret) is covered by `terraform-gcp/.gitignore` and was never staged.
- GCP names/text in the Operations Console UI already correctly say "GKE Operations Lab (GCP Clone)", reference the actual GCP project/Artifact Registry path, and the Guide tab documents the real GCP topology; the PONG button already used the relative path `/pong` (verified against the live served page, not just the source).

## Known, accepted limitations of this clone

- HTTP only, no TLS — per your explicit scope (no DNS, no Cloudflare, no cert).
- Single node, no HA — same as the Azure lab's own design intent.
- Local Terraform state (no remote backend) — appropriate for a throwaway, single-operator experiment.
- The pre-existing "app never retries its DB connection after a failed startup" limitation (see incident #1) is unchanged from Azure; fixing it was out of scope for this migration.

## Cost while running

Roughly the same order as originally estimated: 1× e2-medium node + one GCP Load Balancer + 5Gi persistent disk + Artifact Registry storage ≈ **€2–3/day**, accruing continuously until torn down.

## Cleanup (when you're done experimenting)

```bash
# From the repo root, on any branch:
cd terraform-gcp
terraform destroy   # removes VPC, GKE cluster, Artifact Registry, IAM, Secret Manager secret

# Belt-and-suspenders — deletes the entire project outright, including
# anything created imperatively (ingress-nginx, the bootstrapped RBAC
# objects, the SA key file's corresponding GCP-side key) that Terraform
# itself never tracked:
gcloud projects delete migration-lab-gcp-clone
```
Either step alone stops all billing; running both is the cleanest guarantee that nothing is left behind. The `gcp-exact-clone` git branch and the local `terraform-gcp/.secrets/gha-deploy-key.json` file can be deleted afterward at your convenience — neither costs anything to leave in place.

## Files changed on this branch (relative to `main`)

- `terraform-gcp/` — new (providers, variables, main, outputs, lockfile, gitignore)
- `.github/workflows/deploy-gcp.yml` — new
- `helm/migration-app/values-gcp.yaml` — new
- `helm/migration-app/values.yaml` — added `operations.manageRbac` (default `true`)
- `helm/migration-app/templates/operations-rbac.yaml` — gated by `manageRbac` instead of `enabled`
- `helm/pong-app/values-gcp.yaml` — new
- `helm/pong-app/values.yaml` — added `ingress.azureHost` (default = Azure hostname)
- `helm/pong-app/templates/ingress.yaml` — Azure host/TLS rule now conditional on `azureHost`
- `helm/pong-app/templates/deployment.yaml` — minor GCP-image-path compatibility fix
- `app/Dockerfile` — `apt-get upgrade` at build time
- `app/static/index.html`, `pong/index.html` — GCP-accurate branding/guide content
