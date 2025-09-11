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
  description   = "News Semantic API images (smoke-test)"
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


# WIF: Pool + Provider OIDC de GitHub - evitar llaves JSON. El pipeline se autentica por OIDC
resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub OIDC Pool"
  depends_on                = [google_project_service.services]
}
#Toma y confía en los tokens de git hub actions
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub Provider"

  # Mapeos de claims -> atributos opcionales
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
    "attribute.actor"      = "assertion.actor"
  }

  # Condición que usa *claims reales* del token OIDC de GitHub
  attribute_condition = "assertion.repository == '${var.github_repo}' && assertion.ref == '${var.github_ref}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  depends_on = [google_project_service.services]
}


# Service Account que asumirá GitHub Actions
resource "google_service_account" "ci_deployer" {
  account_id   = "ci-deployer"
  display_name = "CI Deployer"
}

# Permisos mínimos para build+deploy
resource "google_project_iam_member" "ar_writer" {
  project    = var.project_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.ci_deployer.email}"
  depends_on = [google_project_service.services]
}

resource "google_project_iam_member" "gke_deployer" {
  project    = var.project_id
  role       = "roles/container.developer"
  member     = "serviceAccount:${google_service_account.ci_deployer.email}"
  depends_on = [google_project_service.services]
}

# Binding WIF: permite a tu repo asumir la SA (reemplaza OWNER/REPO)

resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.ci_deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repo}"
}


data "google_project" "project" {}
output "wif_provider" {
  value = "projects/${data.google_project.project.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github_pool.workload_identity_pool_id}/providers/${google_iam_workload_identity_pool_provider.github_provider.workload_identity_pool_provider_id}"
}
output "ci_service_account" { value = google_service_account.ci_deployer.email }
