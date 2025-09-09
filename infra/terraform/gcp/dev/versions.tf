terraform {
  backend "gcs" {
    bucket = "tfstate-news-semantic-api-471506"   
    prefix = "terraform/state/dev"
  }
  required_version = ">= 1.6.0"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.36" }
  }
}

