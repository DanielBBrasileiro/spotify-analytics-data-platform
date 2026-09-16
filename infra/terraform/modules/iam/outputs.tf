output "lambda_role_arn" {
  value = aws_iam_role.lambda.arn
}

output "glue_role_arn" {
  value = aws_iam_role.glue.arn
}

output "snowflake_role_arn" {
  value = aws_iam_role.snowflake.arn
}
