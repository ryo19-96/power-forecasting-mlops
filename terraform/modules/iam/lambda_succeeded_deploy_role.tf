resource "aws_iam_role" "succeeded_deploy_role" {
  name = "succeeded-deploy-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action    = "sts:AssumeRole",
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

resource "aws_iam_policy" "succeeded_deploy_policy" {
  name = "succeeded-deploy-ssm-sagemaker"
  policy = jsonencode({
    Version : "2012-10-17",
    Statement : [
      {
        Effect : "Allow",
        Action : [
          "ssm:PutParameter",
          "ssm:GetParameter",
          "sagemaker:DescribeEndpoint"
        ],
        Resource : "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "succeeded_deploy_policy_attach" {
  role       = aws_iam_role.succeeded_deploy_role.name
  policy_arn = aws_iam_policy.succeeded_deploy_policy.arn
}

output "succeeded_deploy_role" {
  value = aws_iam_role.succeeded_deploy_role
}
