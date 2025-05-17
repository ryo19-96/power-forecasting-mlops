# lambda 関数定義
variable "lambda_email_role_arn" {
  type = string
}

resource "aws_lambda_function" "send_approval_email" {
  function_name    = "send-approval-email-${terraform.workspace}"
  filename         = "../send_approval_email.zip"
  source_code_hash = filebase64sha256("../send_approval_email.zip")
  runtime          = "python3.10"
  role             = var.lambda_email_role_arn
  handler          = "send_approval_email.lambda_handler" # Lambda関数のエントリポイント
  # Lambda の中で使う環境変数
  environment {
    variables = {
      APPROVER_EMAIL = var.approval_email_address
      API_URL        = "https://example.com/approve" # API Gateway の URL
    }
  }
}

output "send_approval_email_lambda" {
  value = aws_lambda_function.send_approval_email
}
