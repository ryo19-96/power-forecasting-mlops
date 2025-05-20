
# === model registryで"PendingManualApproval"の状態になったときに、Lambdaを呼び出すEventBridgeの設定 ===
variable "aws_lambda_function" {
  type = object({
    arn           = string
    function_name = string
  })
}

resource "aws_cloudwatch_event_rule" "model_on_pending_manual" {
  name = "sagemaker-model-pending-approval"
  event_pattern = jsonencode({
    "source" : ["aws.sagemaker"],
    "detail-type" : ["SageMaker Model Package State Change"],
    "detail" : {
      "ModelApprovalStatus" : ["PendingManualApproval"],
      "ModelPackageGroupName" : ["PowerForecastPackageGroup"]
    }
  })
}

# イベントが発生したとき呼び出す Lambda 関数を指定する（ターゲットとしてLambdaを指定するため）
resource "aws_cloudwatch_event_target" "send_approval_email" {
  rule = aws_cloudwatch_event_rule.model_on_pending_manual.name
  arn  = var.aws_lambda_function.arn
}

# Lambda 関数に対して、EventBridge からの呼び出しを許可する設定
resource "aws_lambda_permission" "allow_eventbridge" {
  action        = "lambda:InvokeFunction"
  function_name = var.aws_lambda_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.model_on_pending_manual.arn
}

# === deployで成功したときに、Lambdaを呼び出すEventBridgeの設定 ===
variable "lambda_succeeded_deploy_function" {
  type = object({
    arn           = string
    function_name = string
  })
}
resource "aws_cloudwatch_event_rule" "deploy_succeeded" {
  name = "deploy-succeeded-rule"
  event_pattern = jsonencode({
    "source"      = ["aws.sagemaker"],
    "detail-type" = ["SageMaker Endpoint State Change"],
    "detail" = {
      "EndpointStatus" : ["IN_SERVICE"]
    }
  })
}

resource "aws_cloudwatch_event_target" "result_lambda_target" {
  rule = aws_cloudwatch_event_rule.deploy_succeeded.name
  arn  = var.lambda_succeeded_deploy_function.arn
}

resource "aws_lambda_permission" "allow_eventbridge_invoke" {
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_succeeded_deploy_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.deploy_succeeded.arn
}


