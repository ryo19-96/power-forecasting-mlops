variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "emr_etl_exec_role_arn" {
  type = string
}

variable "emr_app_id" {
  type = string
}

variable "region" {
  type = string
}

variable "account_id" {
  type = string
}

variable "enable_nat_gateway" {
  type = bool
}

resource "aws_iam_policy" "mwaa_emr_serverless" {
  name = "mwaa-emr-serverless"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "AllowEMRServerless",
        Effect = "Allow",
        Action = [
          "emr-serverless:GetApplication",
          "emr-serverless:StartApplication",
          "emr-serverless:StopApplication",
          "emr-serverless:ListApplications",
          "emr-serverless:StartJobRun",
          "emr-serverless:GetJobRun",
          "emr-serverless:CancelJobRun",
          "emr-serverless:ListJobRuns",
        ],
        Resource = [
          "arn:aws:emr-serverless:${var.region}:${var.account_id}:/applications/${var.emr_app_id}",
          "arn:aws:emr-serverless:${var.region}:${var.account_id}:/applications/${var.emr_app_id}/jobruns/*"
        ]
      },
      {
        Sid : "AllowPassRole",
        Effect   = "Allow",
        Action   = "iam:PassRole",
        Resource = var.emr_etl_exec_role_arn,
      },
      {
        Sid    = "AllowDynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = "*"
      },
    ]
  })
}

# aws-iaのMWAA モジュール呼び出し
# MWAAはNAT必須なのでenable_nat_gatewayがtrueのときのみ実行されるようにする
module "mwaa" {
  count   = var.enable_nat_gateway ? 1 : 0
  source  = "aws-ia/mwaa/aws" # terraform registryのモジュール
  version = "0.0.6"

  name              = "power-forecast-mwaa-${terraform.workspace}"
  airflow_version   = "2.6.3"
  environment_class = "mw1.small"

  # ワーカー
  min_workers = 1
  max_workers = 5

  # Airflow 設定
  create_s3_bucket       = true
  dag_s3_path            = "dags"
  requirements_s3_path   = "requirements.txt"
  startup_script_s3_path = "startup.sh"

  # ネットワーク
  vpc_id             = var.vpc_id
  private_subnet_ids = var.private_subnet_ids

  webserver_access_mode = "PUBLIC_ONLY"

  # Airflow UI 接続許可CIDR
  source_cidr = ["0.0.0.0/0"]

  # IAM ロール
  iam_role_additional_policies = {
    "s3-access"             = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
    "logs-access"           = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
    "emr-serverless-access" = aws_iam_policy.mwaa_emr_serverless.arn
  }
}
