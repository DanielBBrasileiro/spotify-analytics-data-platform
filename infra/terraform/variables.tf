variable "aws_region" {
  description = "AWS region for the low-cost development stack."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project identifier used in resource names and tags."
  type        = string
  default     = "spotify-analytics"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "project_tag" {
  description = "Project tag required by the portfolio infrastructure contract."
  type        = string
  default     = "SpotifyAnalyticsDataPlatform"

  validation {
    condition     = length(trimspace(var.project_tag)) > 0
    error_message = "project_tag must not be empty."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.environment))
    error_message = "environment must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "lake_bucket_name" {
  description = "Optional globally unique lake bucket name. Empty uses <project>-<environment>-<account-id>."
  type        = string
  default     = ""
}

variable "force_destroy_lake" {
  description = "Allow complete teardown of the development lake, including versioned runtime artifacts."
  type        = bool
  default     = true
}

variable "spotify_credentials_secret_arn" {
  description = "ARN of the existing Secrets Manager secret containing Spotify client_id, client_secret, and refresh_token."
  type        = string

  validation {
    condition     = can(regex("^arn:aws[a-zA-Z-]*:secretsmanager:", var.spotify_credentials_secret_arn))
    error_message = "spotify_credentials_secret_arn must be a Secrets Manager ARN."
  }
}

variable "snowflake_iam_user_arn" {
  description = "Snowflake-generated AWS IAM user ARN shown by DESC INTEGRATION for the storage integration."
  type        = string

  validation {
    condition     = can(regex("^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:user/", var.snowflake_iam_user_arn))
    error_message = "snowflake_iam_user_arn must be an AWS IAM user ARN."
  }
}

variable "snowflake_external_id" {
  description = "Snowflake-generated STORAGE_AWS_EXTERNAL_ID used in the storage-role trust policy."
  type        = string
  sensitive   = true

  validation {
    condition     = length(trimspace(var.snowflake_external_id)) >= 2
    error_message = "snowflake_external_id must not be empty."
  }
}

variable "lambda_artifact_key" {
  description = "S3 key for the pre-built Lambda deployment zip in the lake artifacts prefix."
  type        = string
  default     = "artifacts/lambda/spotify-ingestion.zip"

  validation {
    condition     = startswith(var.lambda_artifact_key, "artifacts/") && endswith(var.lambda_artifact_key, ".zip")
    error_message = "lambda_artifact_key must be a .zip object under artifacts/."
  }
}

variable "lambda_timeout_seconds" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 30

  validation {
    condition     = var.lambda_timeout_seconds >= 1 && var.lambda_timeout_seconds <= 60
    error_message = "lambda_timeout_seconds must be between 1 and 60."
  }
}

variable "lambda_memory_size_mb" {
  description = "Lambda memory size in MB."
  type        = number
  default     = 256

  validation {
    condition     = var.lambda_memory_size_mb >= 128 && var.lambda_memory_size_mb <= 1024
    error_message = "lambda_memory_size_mb must be between 128 and 1024."
  }
}

variable "glue_script_key" {
  description = "S3 key for the Glue entrypoint under the artifacts prefix."
  type        = string
  default     = "artifacts/glue/bronze_to_silver_curation.py"
}

variable "glue_library_key" {
  description = "S3 key for the pre-built Glue Python library zip containing the glue package."
  type        = string
  default     = "artifacts/glue/spotify-glue-lib.zip"
}

variable "glue_number_of_workers" {
  description = "Number of G.1X Glue workers; two is the minimum low-cost Spark shape."
  type        = number
  default     = 2

  validation {
    condition     = var.glue_number_of_workers >= 2 && var.glue_number_of_workers <= 5
    error_message = "glue_number_of_workers must be between 2 and 5."
  }
}

variable "glue_timeout_minutes" {
  description = "Maximum Glue job runtime in minutes."
  type        = number
  default     = 15

  validation {
    condition     = var.glue_timeout_minutes >= 1 && var.glue_timeout_minutes <= 60
    error_message = "glue_timeout_minutes must be between 1 and 60."
  }
}

variable "monthly_budget_usd" {
  description = "Monthly AWS cost budget in USD."
  type        = number
  default     = 20

  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "monthly_budget_usd must be greater than zero."
  }
}

variable "budget_notification_email" {
  description = "Email that receives actual and forecast budget alerts."
  type        = string

  validation {
    condition     = can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.budget_notification_email))
    error_message = "budget_notification_email must be a valid email address."
  }
}

variable "additional_tags" {
  description = "Additional tags merged into every supported AWS resource."
  type        = map(string)
  default     = {}
}
