output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "zone" {
  value = var.zone
}

output "gke_cluster_name" {
  value = google_container_cluster.main.name
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
}

output "github_actions_sa" {
  value = google_service_account.github_actions.email
}

output "postgres_password" {
  value     = random_password.postgres.result
  sensitive = true
}
