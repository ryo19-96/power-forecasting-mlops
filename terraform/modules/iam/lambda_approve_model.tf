# approve後の以下の処理を行うIAMロール
# ①Lambdaでモデルのstatusを"approved" ②deployment_pipelineを起動
resource "aws_iam_role" "lambda_approve_model_role" {
  name = "lambda-approve_model-role-${terraform.workspace}"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          "Effect" : "Allow",
          "Principal" : {
            "Service" : "lambda.amazonaws.com"
          },
          "Action" : "sts:AssumeRole"
        },
      ]
    }
  )
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

resource "aws_iam_policy" "lambda_approve_model_policy" {
  name = "lambda-approve_model-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = [
        "sagemaker:UpdateModelPackage",
        "sagemaker:StartPipelineExecution",
        "ssm:PutParameter",
        "ssm:GetParameter"
      ],
      Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogStream",
          "logs:CreateLogGroup",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      },
    ]
  })
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_approve_model_attach" {
  role       = aws_iam_role.lambda_approve_model_role.name
  policy_arn = aws_iam_policy.lambda_approve_model_policy.arn
}

output "lambda_approve_model_role" {
  value = aws_iam_role.lambda_approve_model_role
}
