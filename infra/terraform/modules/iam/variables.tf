variable "name_prefix" {
  type = string
}

variable "lake_bucket_arn" {
  type = string
}

variable "lambda_log_group_arn" {
  type = string
}

variable "glue_log_group_arns" {
  type = list(string)
}

variable "spotify_credentials_secret_arn" {
  type = string
}

variable "snowflake_iam_user_arn" {
  type = string
}

variable "snowflake_external_id" {
  type      = string
  sensitive = true
}
