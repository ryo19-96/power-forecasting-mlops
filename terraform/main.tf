terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-northeast-1"
}

resource "aws_s3_bucket" "power-forecasting-mlops" {
  bucket        = "power-forecasting-mlops-${terraform.workspace}"
  force_destroy = true
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

resource "aws_s3_bucket_public_access_block" "block_public_access" {
  bucket = aws_s3_bucket.power-forecasting-mlops.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
