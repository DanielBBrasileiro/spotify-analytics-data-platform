data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  bucket_name = var.lake_bucket_name != "" ? var.lake_bucket_name : "${local.name_prefix}-${data.aws_caller_identity.current.account_id}"

  common_tags = merge(
    {
      Project     = var.project_tag
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.additional_tags,
  )
}

module "lake" {
  source = "./modules/s3"

  bucket_name   = local.bucket_name
  force_destroy = var.force_destroy_lake
}

module "monitoring" {
  source = "./modules/monitoring"

  lambda_function_name = "${local.name_prefix}-spotify-ingestion"
  retention_in_days    = 7
  budget_name          = "${local.name_prefix}-monthly-cost"
  monthly_budget_usd   = var.monthly_budget_usd
  notification_email   = var.budget_notification_email
}

module "iam" {
  source = "./modules/iam"

  name_prefix                    = local.name_prefix
  lake_bucket_arn                = module.lake.bucket_arn
  lambda_log_group_arn           = module.monitoring.lambda_log_group_arn
  glue_log_group_arns            = module.monitoring.glue_log_group_arns
  spotify_credentials_secret_arn = var.spotify_credentials_secret_arn
  snowflake_iam_user_arn         = var.snowflake_iam_user_arn
  snowflake_external_id          = var.snowflake_external_id
}

module "lambda" {
  source = "./modules/lambda"

  function_name                  = "${local.name_prefix}-spotify-ingestion"
  role_arn                       = module.iam.lambda_role_arn
  artifact_bucket                = module.lake.bucket_name
  artifact_key                   = var.lambda_artifact_key
  environment                    = var.environment
  lake_bucket_name               = module.lake.bucket_name
  spotify_credentials_secret_arn = var.spotify_credentials_secret_arn
  timeout_seconds                = var.lambda_timeout_seconds
  memory_size_mb                 = var.lambda_memory_size_mb

  depends_on = [module.monitoring]
}

module "glue" {
  source = "./modules/glue"

  job_name          = "${local.name_prefix}-bronze-to-silver"
  role_arn          = module.iam.glue_role_arn
  lake_bucket_name  = module.lake.bucket_name
  script_s3_key     = var.glue_script_key
  library_s3_key    = var.glue_library_key
  number_of_workers = var.glue_number_of_workers
  timeout_minutes   = var.glue_timeout_minutes

  depends_on = [module.monitoring]
}
