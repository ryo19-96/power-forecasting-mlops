variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

# aws-iaのMWAA モジュール呼び出し
module "mwaa" {
  source  = "aws-ia/mwaa/aws" # terraform registryのモジュール
  version = "0.0.6"

  name              = "power-forecast-mwaa-${terraform.workspace}"
  airflow_version   = "2.6.3"
  environment_class = "mw1.small"

  # ワーカー
  min_workers = 1
  max_workers = 5

  # DAG/プラグイン用バケット
  create_s3_bucket     = true # モジュールに作らせる
  dag_s3_path          = "dags"
  requirements_s3_path = "requirements.txt"

  # ネットワーク
  vpc_id             = var.vpc_id
  private_subnet_ids = var.private_subnet_ids

  # Airflow UI 接続許可CIDR
  source_cidr = ["0.0.0.0/0"]

  # IAM ロール
  iam_role_additional_policies = {
    "s3-access"   = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
    "logs-access" = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
  }
}
