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
  source                         = "./modules/lambda"
  lambda_email_role_arn          = module.iam.lambda_email_role.arn
  lambda_update_package_role_arn = module.iam.lambda_update_package_role.arn
  approval_email_address         = var.approval_email_address
  api_gateway_url                = module.api_gateway.approve_api_url
  lambda_deploy_role_arn         = module.iam.lambda_deploy_role.arn
  pipeline_exec_role_arn         = module.iam.power_forecasting_role_arn
}

module "api_gateway" {
  source              = "./modules/api_gateway"
  aws_lambda_function = module.lambda.update_package_lambda
}

module "eventbridge" {
  source                 = "./modules/eventbridge"
  aws_lambda_function    = module.lambda.send_approval_email_lambda
  lambda_deploy_function = module.lambda.deploy_serverless_lambda
}
