# Lambdaでモデルパッケージを更新する用IAMロール
resource "aws_iam_role" "lambda_update_package_role" {
  name = "lambda-update-package-role-${terraform.workspace}"
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

resource "aws_iam_policy" "lambda_update_package_policy" {
  name = "lambda-update-package-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = ["sagemaker:UpdateModelPackage"],
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

resource "aws_iam_role_policy_attachment" "lambda_update_package_attach" {
  role       = aws_iam_role.lambda_update_package_role.name
  policy_arn = aws_iam_policy.lambda_update_package_policy.arn
}

output "lambda_update_package_role" {
  value = aws_iam_role.lambda_update_package_role
}
