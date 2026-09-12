# GCP clone of the Azure migration lab (terraform/main.tf). Mirrors:
#   azurerm_virtual_network/subnet -> google_compute_network/subnetwork
#   azurerm_container_registry    -> google_artifact_registry_repository
#   azurerm_kubernetes_cluster    -> google_container_cluster
#   Azure Workload Identity + Key Vault CSI -> GKE Workload Identity + Secret Manager CSI addon

resource "google_compute_network" "main" {
  name                    = "vpc-migration-lab"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "gke" {
  name          = "snet-gke"
  ip_cidr_range = "10.20.1.0/24"
  region        = var.region
  network       = google_compute_network.main.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.21.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.22.0.0/20"
  }
}

# GKE on a custom (non-default) VPC needs an explicit internal-allow rule -
# the default network's pre-created "default-allow-internal" doesn't exist here.
resource "google_compute_firewall" "allow_internal" {
  name    = "allow-internal-migration-lab"
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.20.1.0/24", "10.21.0.0/16", "10.22.0.0/20"]
}

# GCLB health checks for the nginx-ingress Service (type LoadBalancer) come
# from these two well-known Google-owned ranges.
resource "google_compute_firewall" "allow_health_checks" {
  name    = "allow-gclb-health-checks"
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
  }

  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
}

resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "migration-lab"
  format        = "DOCKER"
  description   = "GCP clone of acrmigrationlab (Azure ACR)"
}

resource "google_container_cluster" "main" {
  name     = "gke-migration-lab"
  location = var.zone

  network    = google_compute_network.main.id
  subnetwork = google_compute_subnetwork.gke.id

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  remove_default_node_pool = true
  initial_node_count       = 1

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  deletion_protection = false
}

# Mirrors the AKS default_node_pool (1 node, Standard_B2s_v2 ~ 2 vCPU/4GB).
resource "google_container_node_pool" "system" {
  name       = "system"
  cluster    = google_container_cluster.main.id
  node_count = 1

  node_config {
    machine_type = "e2-medium"
    disk_size_gb = 30
    disk_type    = "pd-standard"

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }

  upgrade_settings {
    max_surge       = 1
    max_unavailable = 0
  }
}

# The GKE node service account needs to pull images from Artifact Registry -
# the direct equivalent of the AcrPull role assignment on the AKS kubelet identity.
resource "google_project_iam_member" "node_pull" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

data "google_project" "current" {
  project_id = var.project_id
}

# Postgres password: generated fresh for this experiment (never copied from
# Azure), stored in Secret Manager as the canonical value (GCP equivalent of
# Azure Key Vault), and delivered into the cluster as a plain Kubernetes
# Secret afterwards - the GKE Secret Manager CSI addon isn't exposed by this
# provider version, so a CSI mount isn't used here.
resource "random_password" "postgres" {
  length  = 24
  special = false
}

resource "google_secret_manager_secret" "postgres_password" {
  secret_id = "postgres-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "postgres_password" {
  secret      = google_secret_manager_secret.postgres_password.id
  secret_data = random_password.postgres.result
}

# Dedicated least-privilege service account for GitHub Actions CI/CD -
# equivalent to the AZURE_CREDENTIALS service principal.
resource "google_service_account" "github_actions" {
  account_id   = "github-actions-deploy"
  display_name = "GitHub Actions deploy (GCP clone)"
}

resource "google_project_iam_member" "gha_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "gha_gke_developer" {
  project = var.project_id
  # container.developer is deliberately the ceiling for this SA: it can
  # build/push images and run `helm upgrade` for the application workloads,
  # but cannot patch cluster-scoped or namespaced RBAC objects (Role/
  # RoleBinding/ClusterRole/ClusterRoleBinding). Those are bootstrapped once
  # by an administrative identity instead (see
  # helm/migration-app/templates/operations-rbac.yaml's `manageRbac` gate,
  # false in values-gcp.yaml, and AUTONOMOUS_MIGRATION_REPORT.md) so the
  # regular CI/CD deploy identity never needs cluster-admin-adjacent rights.
  role   = "roles/container.developer"
  member = "serviceAccount:${google_service_account.github_actions.email}"
}
