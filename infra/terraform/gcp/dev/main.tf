# Habilita APIs necesarias
resource "google_project_service" "services" {
  for_each = toset([
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com"
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Artifact Registry (Docker)
resource "google_artifact_registry_repository" "repo" {
  location      = var.location
  repository_id = var.repo_name
  description   = "News Semantic API images"
  format        = "DOCKER"
  depends_on    = [google_project_service.services]
}

# GKE Autopilot
resource "google_container_cluster" "autopilot" {
  name                = var.cluster_name
  location            = var.region
  project             = var.project_id
  enable_autopilot    = true
  deletion_protection = false

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  depends_on = [google_project_service.services]
}
