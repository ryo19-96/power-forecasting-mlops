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

data "aws_caller_identity" "current" {}

module "s3" {
  source = "./modules/s3"
}

module "iam" {
  source     = "./modules/iam"
  account_id = data.aws_caller_identity.current.account_id
}

module "lambda" {
  source                           = "./modules/lambda"
  lambda_email_role_arn            = module.iam.lambda_email_role.arn
  lambda_approve_model_role_arn    = module.iam.lambda_approve_model_role.arn
  approval_email_address           = var.approval_email_address
  api_gateway_url                  = module.api_gateway.approve_api_url
  pipeline_exec_role_arn           = module.iam.power_forecasting_role_arn # sagemakerの実行ロール
  lambda_succeeded_deploy_role_arn = module.iam.succeeded_deploy_role.arn
  # power_usage zip 解凍, weather_data csv 抽出用
  extract_bucket_name          = module.s3.extract_bucket_name
  raw_bucket                   = module.s3.raw_bucket
  lambda_extract_data_role_arn = module.iam.extract_data_role.arn
}


module "api_gateway" {
  source              = "./modules/api_gateway"
  aws_lambda_function = module.lambda.approve_model_lambda
}

module "eventbridge" {
  source                           = "./modules/eventbridge"
  aws_lambda_function              = module.lambda.send_approval_email_lambda
  lambda_succeeded_deploy_function = module.lambda.succeeded_deploy_lambda
}

module "dynamodb" {
  source = "./modules/dynamodb"
}

module "network" {
  source             = "./modules/network"
  region             = var.aws_region
  azs                = var.azs
  vpc_cidr           = var.vpc_cidr
  enable_nat_gateway = var.enable_nat_gateway
}

module "mwaa" {
  source                = "./modules/mwaa"
  vpc_id                = module.network.vpc_id
  private_subnet_ids    = module.network.private_subnet_ids
  emr_etl_exec_role_arn = module.iam.emr_etl_exec_role.arn
  emr_app_id            = module.emr.emr_app_id
  region                = var.aws_region
  account_id            = data.aws_caller_identity.current.account_id
  enable_nat_gateway    = var.enable_nat_gateway
}

module "emr" {
  source                = "./modules/emr"
  emr_etl_exec_role_arn = module.iam.emr_etl_exec_role.arn
}

module "feature_store" {
  source                          = "./modules/feature_store"
  offline_bucket                  = module.s3.offline_bucket
  sagemaker_featurestore_role_arn = module.iam.sagemaker_featurestore_role_arn
}
