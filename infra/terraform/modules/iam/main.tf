data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.name_prefix}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "WriteBronzeOnly"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${var.lake_bucket_arn}/bronze/spotify/*"]
  }

  statement {
    sid       = "ReadSpotifyCredentials"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.spotify_credentials_secret_arn]
  }

  statement {
    sid       = "WriteLambdaLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${var.lambda_log_group_arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${var.name_prefix}-lambda-runtime"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

data "aws_iam_policy_document" "glue_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue" {
  name               = "${var.name_prefix}-glue"
  assume_role_policy = data.aws_iam_policy_document.glue_assume.json
}

data "aws_iam_policy_document" "glue" {
  statement {
    sid       = "GetLakeLocation"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation"]
    resources = [var.lake_bucket_arn]
  }

  statement {
    sid       = "ListLakePrefixes"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.lake_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "bronze/*",
        "silver/*",
        "artifacts/glue/*",
        "metadata/*",
      ]
    }
  }

  statement {
    sid       = "ReadBronzeAndGlueArtifacts"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.lake_bucket_arn}/bronze/*", "${var.lake_bucket_arn}/artifacts/glue/*"]
  }

  statement {
    sid       = "ManageSilverObjects"
    effect    = "Allow"
    actions   = ["s3:AbortMultipartUpload", "s3:DeleteObject", "s3:GetObject", "s3:PutObject"]
    resources = ["${var.lake_bucket_arn}/silver/*"]
  }

  statement {
    sid       = "ManageCompletionMetadata"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${var.lake_bucket_arn}/metadata/*"]
  }

  statement {
    sid       = "WriteGlueLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [for arn in var.glue_log_group_arns : "${arn}:*"]
  }
}

resource "aws_iam_role_policy" "glue" {
  name   = "${var.name_prefix}-glue-runtime"
  role   = aws_iam_role.glue.id
  policy = data.aws_iam_policy_document.glue.json
}

data "aws_iam_policy_document" "snowflake_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [var.snowflake_iam_user_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.snowflake_external_id]
    }
  }
}

resource "aws_iam_role" "snowflake" {
  name               = "${var.name_prefix}-snowflake-storage"
  assume_role_policy = data.aws_iam_policy_document.snowflake_assume.json
}

data "aws_iam_policy_document" "snowflake" {
  statement {
    sid       = "GetLakeLocation"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation"]
    resources = [var.lake_bucket_arn]
  }

  statement {
    sid       = "ListSilverPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.lake_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["silver", "silver/*"]
    }
  }

  statement {
    sid       = "ReadSilverObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${var.lake_bucket_arn}/silver/*"]
  }
}

resource "aws_iam_role_policy" "snowflake" {
  name   = "${var.name_prefix}-snowflake-silver-read"
  role   = aws_iam_role.snowflake.id
  policy = data.aws_iam_policy_document.snowflake.json
}
