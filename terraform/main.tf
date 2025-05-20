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
  source                           = "./modules/lambda"
  lambda_email_role_arn            = module.iam.lambda_email_role.arn
  lambda_approve_model_role_arn    = module.iam.lambda_approve_model_role.arn
  approval_email_address           = var.approval_email_address
  api_gateway_url                  = module.api_gateway.approve_api_url
  pipeline_exec_role_arn           = module.iam.power_forecasting_role_arn # sagemakerの実行ロール
  lambda_succeeded_deploy_role_arn = module.iam.succeeded_deploy_role.arn
}

module "api_gateway" {
  source              = "./modules/api_gateway"
  aws_lambda_function = module.lambda.approve_model_lambda
}

module "eventbridge" {
  source              = "./modules/eventbridge"
  aws_lambda_function = module.lambda.send_approval_email_lambda
  # lambda_model_approved_function   = module.lambda.approve_model_lambda
  lambda_succeeded_deploy_function = module.lambda.succeeded_deploy_lambda
}
