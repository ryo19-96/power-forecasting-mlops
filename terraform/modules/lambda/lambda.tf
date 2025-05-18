# email送信用 lambda 関数定義
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
  value = aws_lambda_function.send_approval_email
}

# emailでの承認後用 lambda 関数定義
variable "lambda_update_package_role_arn" {
  type = string
}

resource "aws_lambda_function" "update_package" {
  function_name    = "update-package-lambda-${terraform.workspace}"
  filename         = "../lambda/update_package.zip"
  source_code_hash = filebase64sha256("../lambda/update_package.zip")
  handler          = "update_package.lambda_handler"
  runtime          = "python3.10"
  role             = var.lambda_update_package_role_arn
}

output "update_package_lambda" {
  value = {
    arn           = aws_lambda_function.update_package.arn
    function_name = aws_lambda_function.update_package.function_name
    invoke_arn    = aws_lambda_function.update_package.invoke_arn
  }
}
