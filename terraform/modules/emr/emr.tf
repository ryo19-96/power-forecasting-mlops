variable "emr_etl_exec_role_arn" {
  type = string
}

resource "aws_emrserverless_application" "etl" {
  name          = "power_weather_etl"
  release_label = "emr-6.15.0"
  type          = "spark"

  maximum_capacity {
    cpu    = "2 vCPU"
    memory = "8 GB"
  }
}

output "emr_app_id" {
  value = aws_emrserverless_application.etl.id
}

# EMR Serverless Applicationで使用する値をparameter storeに保存
resource "aws_ssm_parameter" "emr_app_id" {
  name  = "/power-forecasting/dev/emr/app_id"
  type  = "String"
  value = aws_emrserverless_application.etl.id
}

resource "aws_ssm_parameter" "emr_exec_role" {
  name  = "/power-forecasting/dev/emr/execution_role_arn"
  type  = "String"
  value = var.emr_etl_exec_role_arn
}
