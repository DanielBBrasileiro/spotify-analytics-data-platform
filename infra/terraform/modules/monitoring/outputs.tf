output "lambda_log_group_arn" {
  value = aws_cloudwatch_log_group.lambda.arn
}

output "glue_log_group_arns" {
  value = [
    aws_cloudwatch_log_group.glue_error.arn,
    aws_cloudwatch_log_group.glue_output.arn,
  ]
}

output "budget_name" {
  value = aws_budgets_budget.monthly.name
}
