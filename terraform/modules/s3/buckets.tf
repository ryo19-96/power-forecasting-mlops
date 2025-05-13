resource "aws_s3_bucket" "power_forecasting_mlops" {
  bucket        = "power-forecasting-mlops-${terraform.workspace}"
  force_destroy = true
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
