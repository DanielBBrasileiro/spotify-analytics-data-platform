variable "lambda_function_name" {
  type = string
}

variable "retention_in_days" {
  type    = number
  default = 7
}

variable "budget_name" {
  type = string
}

variable "monthly_budget_usd" {
  type = number
}

variable "notification_email" {
  type = string
}
