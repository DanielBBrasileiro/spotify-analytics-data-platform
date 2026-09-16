resource "aws_cloudwatch_log_group" "lambda" {
  # checkov:skip=CKV_AWS_338:Seven-day retention is an explicit cost guardrail for ephemeral portfolio telemetry, not a compliance archive.
  # checkov:skip=CKV_AWS_158:Customer-managed KMS encryption is intentionally omitted for low-volume non-secret dev logs to avoid key-management cost/complexity.
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = var.retention_in_days
}

resource "aws_cloudwatch_log_group" "glue_error" {
  # checkov:skip=CKV_AWS_338:Seven-day retention is an explicit cost guardrail for ephemeral portfolio telemetry, not a compliance archive.
  # checkov:skip=CKV_AWS_158:Customer-managed KMS encryption is intentionally omitted for low-volume non-secret dev logs to avoid key-management cost/complexity.
  name              = "/aws-glue/jobs/error"
  retention_in_days = var.retention_in_days
}

resource "aws_cloudwatch_log_group" "glue_output" {
  # checkov:skip=CKV_AWS_338:Seven-day retention is an explicit cost guardrail for ephemeral portfolio telemetry, not a compliance archive.
  # checkov:skip=CKV_AWS_158:Customer-managed KMS encryption is intentionally omitted for low-volume non-secret dev logs to avoid key-management cost/complexity.
  name              = "/aws-glue/jobs/output"
  retention_in_days = var.retention_in_days
}

resource "aws_budgets_budget" "monthly" {
  name         = var.budget_name
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.notification_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.notification_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 90
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.notification_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 90
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.notification_email]
  }
}
