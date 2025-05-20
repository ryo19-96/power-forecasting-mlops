variable "aws_lambda_function" {
  type = object({
    arn           = string
    function_name = string
    invoke_arn    = string
  })
}

# http-api-gateway本体
resource "aws_apigatewayv2_api" "approve_api" {
  name = "model-approve-api"
  # REST APIと比較して、低レイテンシ、低コストなのでHTTP APIを使用する
  protocol_type = "HTTP"
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}
# Lambdaとの接続設定
resource "aws_apigatewayv2_integration" "approve_lambda_integration" {
  api_id = aws_apigatewayv2_api.approve_api.id
  # Lambdaを直接呼び出すプロキシモード
  integration_type       = "AWS_PROXY"
  integration_uri        = var.aws_lambda_function.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}
# エンドポイントのルートを設定
resource "aws_apigatewayv2_route" "approve_route" {
  api_id = aws_apigatewayv2_api.approve_api.id
  # GETメソッドで/approveにアクセスしたときに呼び出す
  route_key = "GET /approve"
  target    = "integrations/${aws_apigatewayv2_integration.approve_lambda_integration.id}"
}

resource "aws_apigatewayv2_stage" "approve_stage" {
  api_id      = aws_apigatewayv2_api.approve_api.id
  name        = "$default"
  auto_deploy = true
}


resource "aws_lambda_permission" "allow_apigw_to_invoke" {
  action        = "lambda:InvokeFunction"
  function_name = var.aws_lambda_function.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.approve_api.execution_arn}/*/*"
}

output "approve_api_url" {
  value = aws_apigatewayv2_api.approve_api.api_endpoint
}
