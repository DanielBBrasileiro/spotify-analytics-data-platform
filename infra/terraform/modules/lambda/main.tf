resource "aws_lambda_function" "ingestion" {
  # checkov:skip=CKV_AWS_50:X-Ray is intentionally omitted from the bounded dev stack to avoid trace cost; structured logs cover the portfolio telemetry contract.
  # checkov:skip=CKV_AWS_117:The public Spotify API requires outbound internet; putting this Lambda in a VPC would add NAT/VPC-endpoint cost without a private dependency.
  # checkov:skip=CKV_AWS_116:The bounded source path uses explicit invocation status/retries; a managed DLQ is a production extension rather than part of this low-cost portfolio slice.
  # checkov:skip=CKV_AWS_173:No secret values are stored in environment variables; only resource identifiers are present, so a customer-managed KMS key is not justified here.
  # checkov:skip=CKV_AWS_272:Code-signing configuration is deferred for this portfolio stack; artifacts are built/versioned in CI and deployment remains an explicit operator action.
  function_name = var.function_name
  description   = "Spotify playlist snapshot ingestion into the Bronze S3 prefix"
  role          = var.role_arn
  runtime       = "python3.12"
  handler       = "extractor.lambda_handler"

  s3_bucket = var.artifact_bucket
  s3_key    = var.artifact_key

  architectures                  = ["x86_64"]
  memory_size                    = var.memory_size_mb
  timeout                        = var.timeout_seconds
  reserved_concurrent_executions = 1

  environment {
    variables = {
      ENVIRONMENT                     = var.environment
      S3_BUCKET_NAME                  = var.lake_bucket_name
      AWS_SECRETS_MANAGER_SECRET_NAME = var.spotify_credentials_secret_arn
    }
  }
}
