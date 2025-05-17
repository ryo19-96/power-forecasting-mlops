terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.17.0"
    }
  }
}
# TODO: version 固定
provider "aws" {
  region = "ap-northeast-1"
}

module "s3" {
  source = "./modules/s3"
}

module "iam" {
  source = "./modules/iam"
}

module "lambda" {
  source                 = "./modules/lambda"
  lambda_email_role_arn  = module.iam.lambda_email_role.arn
  approval_email_address = var.approval_email_address
}

# module "api_gateway" {
#   source = "./modules/api_gateway"
# }

module "eventbridge" {
  source              = "./modules/eventbridge"
  aws_lambda_function = module.lambda.send_approval_email_lambda
}
