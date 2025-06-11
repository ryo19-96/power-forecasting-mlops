# nat_gateway, elastic_ipは時間でコストがかかるので、不要なときはfalseにする
# 有効にしたいとき：terraform apply -var="enable_nat_gateway=true"
variable "enable_nat_gateway" {
  type    = bool
  default = false
}

variable "approval_email_address" {
  type    = string
  default = "temp@example.com"
}

variable "aws_region" {
  type    = string
  default = "ap-northeast-1"
}

variable "azs" {
  type    = list(string)
  default = ["ap-northeast-1a", "ap-northeast-1c"]
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

# model_pipeline名
variable "model_pipeline_name" {
  type    = string
  default = "PowerForecastPipeline"
}

variable "feature_group_name" {
  type    = string
  default = "power_forecast_features"
}
