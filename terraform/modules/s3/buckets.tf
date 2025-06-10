resource "aws_s3_bucket" "power_forecasting_mlops" {
  bucket        = "power-forecasting-mlops-${terraform.workspace}"
  force_destroy = true
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

# 生データのbacket
resource "aws_s3_bucket" "raw" {
  bucket = "power-forecasting-raw-data-${terraform.workspace}"
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

output "raw_bucket" {
  value = aws_s3_bucket.raw
}

# zip解凍、csv抽出後のbacket
resource "aws_s3_bucket" "extract" {
  bucket = "power-forecasting-extract-data-${terraform.workspace}"
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

output "extract_bucket_name" {
  value = aws_s3_bucket.extract.bucket
}

# EMRなどで処理した後のデータを保存するbacket
resource "aws_s3_bucket" "processed" {
  bucket = "power-forecasting-processed-data-${terraform.workspace}"
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

resource "aws_s3_bucket_public_access_block" "block_public_access" {
  bucket = aws_s3_bucket.power_forecasting_mlops.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# EMR後のbacket設定 削除のルールは設定しない
resource "aws_s3_bucket_lifecycle_configuration" "processed_lifecycle" {
  bucket = aws_s3_bucket.processed.id
  rule {
    id     = "archive-old-data"
    status = "Enabled"
    # オブジェクトの作成から30日後にアーカイブ（コスト削減のため）
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
}

# EMRのスクリプト用のS3バケット
resource "aws_s3_bucket" "emr_scripts" {
  bucket = "power-forecasting-emr-scripts-${terraform.workspace}"
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

# オフラインストアのS3バケット
resource "aws_s3_bucket" "offline_store" {
  bucket        = "power-forecast-featurestore-offline-${terraform.workspace}"
  force_destroy = true
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}
output "offline_bucket" {
  value = aws_s3_bucket.offline_store.bucket
}

# Athenaのクエリ用のS3バケット
resource "aws_s3_bucket" "athena_query_results" {
  bucket        = "power-forecast-athena-query-results-${terraform.workspace}"
  force_destroy = true
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}
