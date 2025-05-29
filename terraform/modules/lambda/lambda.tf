# === email送信用 lambda 関数定義 ===
variable "lambda_email_role_arn" {
  type = string
}

variable "approval_email_address" {
  type = string
}

variable "api_gateway_url" {
  type = string
}

resource "aws_lambda_function" "send_approval_email" {
  function_name    = "send-approval-email-${terraform.workspace}"
  filename         = "../lambda/send_approval_email.zip"
  source_code_hash = filebase64sha256("../lambda/send_approval_email.zip")
  runtime          = "python3.10"
  role             = var.lambda_email_role_arn
  handler          = "send_approval_email.lambda_handler"
  # Lambda の中で使う環境変数
  environment {
    variables = {
      APPROVER_EMAIL = var.approval_email_address
      # API Gateway の URL
      # ここでのapproveはエンドポイントのルーチで、中身のapprove, rejectはlambdaの中で分けて処理する
      # 変える場合はapi_gateway.tfのroute_keyも変更すること
      API_URL = "${var.api_gateway_url}/approve"
    }
  }
}

output "send_approval_email_lambda" {
  value = {
    arn           = aws_lambda_function.send_approval_email.arn
    function_name = aws_lambda_function.send_approval_email.function_name
  }
}


# === emailでApproveを押した時に動作用 lambda（API Gateway) 関数定義 ===
variable "lambda_approve_model_role_arn" {
  type = string
}
variable "pipeline_exec_role_arn" {
  type = string
}

resource "aws_lambda_function" "approve_model_lambda" {
  function_name    = "approve_model-lambda-${terraform.workspace}"
  filename         = "../lambda/approved_model.zip"
  source_code_hash = filebase64sha256("../lambda/approved_model.zip")
  handler          = "approved_model.lambda_handler"
  runtime          = "python3.10"
  timeout          = 15
  role             = var.lambda_approve_model_role_arn
  environment {
    variables = {
      SAGEMAKER_ROLE  = var.pipeline_exec_role_arn
      DEPLOY_PIPELINE = "PowerForecastDeploymentPipeline"
      ENV             = "${terraform.workspace}"
    }
  }
}

output "approve_model_lambda" {
  value = {
    arn           = aws_lambda_function.approve_model_lambda.arn
    function_name = aws_lambda_function.approve_model_lambda.function_name
    invoke_arn    = aws_lambda_function.approve_model_lambda.invoke_arn
  }
}

# === pipeline成功を検知して結果をParameter Storeに記録する lambda + EventBridge 定義===
variable "lambda_succeeded_deploy_role_arn" {
  type = string
}

resource "aws_lambda_function" "succeeded_deploy" {
  function_name    = "succeeded-deploy-lambda-${terraform.workspace}"
  filename         = "../lambda/succeeded_deploy.zip"
  source_code_hash = filebase64sha256("../lambda/succeeded_deploy.zip")
  handler          = "succeeded_deploy.lambda_handler"
  runtime          = "python3.10"
  timeout          = 6
  role             = var.lambda_succeeded_deploy_role_arn
  environment {
    variables = {
      ENV = "${terraform.workspace}"
    }
  }
}

output "succeeded_deploy_lambda" {
  value = {
    arn           = aws_lambda_function.succeeded_deploy.arn
    function_name = aws_lambda_function.succeeded_deploy.function_name
  }
}

# === power_usageのzipファイルが更新されたとき、S3のzipファイルを解凍するラムダ関数===
variable "extract_bucket_name" {
  type = string
}

variable "raw_bucket" {
  type = object({
    arn    = string
    bucket = string
  })
}

variable "lambda_extract_data_role_arn" {
  type = string
}

resource "aws_lambda_function" "unzip_power_usage" {
  function_name    = "unzip-power-usage-${terraform.workspace}"
  filename         = "../lambda/unzip_power_usage.zip"
  source_code_hash = filebase64sha256("../lambda/unzip_power_usage.zip")
  handler          = "unzip_power_usage.lambda_handler"
  runtime          = "python3.10"
  role             = var.lambda_extract_data_role_arn
  timeout          = 600
  environment {
    variables = {
      BUCKET = var.extract_bucket_name
    }
  }
}

resource "aws_lambda_permission" "allow_s3_trigger_power_usage" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.unzip_power_usage.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.raw_bucket.arn
}

# === weather_fileが更新されたとき、中身を日付毎に抽出するラムダ関数===
resource "aws_lambda_function" "extract_weather_file" {
  function_name    = "extract-weather-file-${terraform.workspace}"
  filename         = "../lambda/extract_weather_data.zip"
  source_code_hash = filebase64sha256("../lambda/extract_weather_data.zip")
  handler          = "extract_weather_data.lambda_handler"
  runtime          = "python3.10"
  role             = var.lambda_extract_data_role_arn
  timeout          = 600
  layers = [
    "arn:aws:lambda:ap-northeast-1:770693421928:layer:Klayers-p310-pandas:24"
  ]
  environment {
    variables = {
      BUCKET = var.extract_bucket_name
    }
  }
}

resource "aws_lambda_permission" "allow_s3_trigger_weather_data" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.extract_weather_file.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.raw_bucket.arn
}

resource "aws_s3_bucket_notification" "s3_trigger_lambda" {
  bucket = var.raw_bucket.bucket

  lambda_function {
    lambda_function_arn = aws_lambda_function.unzip_power_usage.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "power_usage/"
    filter_suffix       = ".zip"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.extract_weather_file.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "weather_data/"
    filter_suffix       = ".csv"
  }

  depends_on = [
    aws_lambda_permission.allow_s3_trigger_power_usage,
    aws_lambda_permission.allow_s3_trigger_weather_data,
  ]
}
