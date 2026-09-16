output "lake_bucket_name" {
  description = "Name of the single S3 data lake bucket."
  value       = module.lake.bucket_name
}

output "lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket."
  value       = module.lake.bucket_arn
}

output "bronze_s3_uri" {
  description = "Bronze landing prefix."
  value       = "s3://${module.lake.bucket_name}/bronze/"
}

output "silver_s3_uri" {
  description = "Silver curated prefix."
  value       = "s3://${module.lake.bucket_name}/silver/"
}

output "artifacts_s3_uri" {
  description = "Deployment-artifact prefix."
  value       = "s3://${module.lake.bucket_name}/artifacts/"
}

output "metadata_s3_uri" {
  description = "Pipeline metadata/completion prefix."
  value       = "s3://${module.lake.bucket_name}/metadata/"
}

output "lambda_function_name" {
  description = "Spotify extraction Lambda function name."
  value       = module.lambda.function_name
}

output "lambda_function_arn" {
  description = "Spotify extraction Lambda function ARN."
  value       = module.lambda.function_arn
}

output "glue_job_name" {
  description = "Glue Bronze-to-Silver job name."
  value       = module.glue.job_name
}

output "lambda_role_arn" {
  description = "Least-privilege Lambda execution role ARN."
  value       = module.iam.lambda_role_arn
}

output "glue_role_arn" {
  description = "Least-privilege Glue execution role ARN."
  value       = module.iam.glue_role_arn
}

output "snowflake_storage_role_arn" {
  description = "AWS role ARN to configure in the Snowflake storage integration."
  value       = module.iam.snowflake_role_arn
}

output "budget_name" {
  description = "AWS Budget tracking the monthly development spend."
  value       = module.monitoring.budget_name
}
