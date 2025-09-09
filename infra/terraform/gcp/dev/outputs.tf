output "artifact_repo" {
  value = "${var.location}-docker.pkg.dev/${var.project_id}/${var.repo_name}"
}
output "cluster_name" {
  value = var.cluster_name
}
output "region" {
  value = var.region
}
