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
