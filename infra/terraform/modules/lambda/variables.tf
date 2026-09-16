variable "function_name" {
  type = string
}

variable "role_arn" {
  type = string
}

variable "artifact_bucket" {
  type = string
}

variable "artifact_key" {
  type = string
}

variable "environment" {
  type = string
}

variable "lake_bucket_name" {
  type = string
}

variable "spotify_credentials_secret_arn" {
  type = string
}

variable "timeout_seconds" {
  type = number
}

variable "memory_size_mb" {
  type = number
}
