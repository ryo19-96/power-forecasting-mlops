# Lambda 用 IAM
resource "aws_iam_role" "lambda_deploy" {
  name = "lambda-deploy-serverless-role-${terraform.workspace}"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          "Effect" : "Allow",
          "Principal" : {
            "Service" : [
              "lambda.amazonaws.com",
              "sagemaker.amazonaws.com"
            ],
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

resource "aws_iam_policy" "lambda_deploy_policy" {
  name = "lambda-deploy-sagemaker-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = [
        "sagemaker:CreateModel",
        "sagemaker:CreateEndpointConfig",
        "sagemaker:CreateEndpoint",
        "sagemaker:UpdateEndpoint",
        "sagemaker:StartPipelineExecution",
        "sagemaker:DescribeEndpoint",
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "s3:GetObject",
        "iam:PassRole",
      ],
      Resource = "*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "logs:CreateLogStream",
          "logs:CreateLogGroup",
          "logs:PutLogEvents"
        ],
        "Resource" : "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow",
        Action = [
          "lambda:InvokeFunction",
        ],
        Resource = "arn:aws:lambda:ap-northeast-1:163817410757:function:deploy-step"
    }, ]
  })
}
resource "aws_iam_role_policy_attachment" "lambda_deploy_attach" {
  role       = aws_iam_role.lambda_deploy.name
  policy_arn = aws_iam_policy.lambda_deploy_policy.arn
}

output "lambda_deploy_role" {
  value = aws_iam_role.lambda_deploy
}
