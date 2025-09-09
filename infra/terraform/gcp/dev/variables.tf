variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "location" {
  type    = string
  default = "us-central1" # Artifact Registry
}

variable "repo_name" {
  type    = string
  default = "news-semantic-api"
}

variable "cluster_name" {
  type    = string
  default = "news-dev-autopilot"
}

variable "github_repo" {
  description = "JorgeEduardo24/news-semantic-api"
  type        = string
}

variable "github_ref" {
  description = "refs/heads/main"
  type        = string
  default     = "refs/heads/main"
}
