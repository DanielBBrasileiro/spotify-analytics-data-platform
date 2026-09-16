variable "job_name" {
  type = string
}

variable "role_arn" {
  type = string
}

variable "lake_bucket_name" {
  type = string
}

variable "script_s3_key" {
  type = string
}

variable "library_s3_key" {
  type = string
}

variable "number_of_workers" {
  type = number
}

variable "timeout_minutes" {
  type = number
}
