terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.17.0"
    }
  }
}

provider "aws" {
  region = "ap-northeast-1"
}

module "s3" {
  source = "./modules/s3"
}

module "iam" {
  source = "./modules/iam"
}

module "api_gateway" {
  source = "./modules/api_gateway"
}

module "lambda" {
  source = "./modules/lambda"
}

module "eventbridge" {
  source = "./modules/eventbridge"
}
