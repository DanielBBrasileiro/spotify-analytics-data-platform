resource "aws_glue_job" "bronze_to_silver" {
  # checkov:skip=CKV_AWS_195:The dev job writes to an SSE-S3 encrypted private lake; a separate KMS-backed Glue security configuration is intentionally outside the low-cost slice.
  name         = var.job_name
  description  = "AWS Glue 5.1 Bronze-to-Silver Spotify curation"
  role_arn     = var.role_arn
  glue_version = "5.1"

  worker_type       = "G.1X"
  number_of_workers = var.number_of_workers
  execution_class   = "FLEX"
  max_retries       = 0
  timeout           = var.timeout_minutes

  execution_property {
    max_concurrent_runs = 1
  }

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.lake_bucket_name}/${var.script_s3_key}"
  }

  default_arguments = {
    "--job-language"                 = "python"
    "--enable-metrics"               = "true"
    "--enable-observability-metrics" = "true"
    "--extra-py-files"               = "s3://${var.lake_bucket_name}/${var.library_s3_key}"
    "--silver-root"                  = "s3://${var.lake_bucket_name}/silver"
    "--output-partitions"            = "1"
  }
}
