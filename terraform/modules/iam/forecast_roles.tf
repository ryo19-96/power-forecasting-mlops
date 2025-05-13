resource "aws_iam_role" "power_forecasting_role" {
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Principal = {
            Service = [
              "sagemaker.amazonaws.com",
            ]
          }
          Action = "sts:AssumeRole"
          Effect = "Allow"
        },
      ]
    }
  )
  force_detach_policies = false
  max_session_duration  = 3600
  name                  = "power-forecasting-role-${terraform.workspace}"
  path                  = "/service-role/"
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

resource "aws_iam_policy" "power_forecasting_policy" {
  name = "power-forecasting-${terraform.workspace}"
  path = "/service-role/"
  policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          # ファイルの取得、リスト、モデルの保存を想定
          Action = [
            "s3:GetObject",
            "s3:ListBucket",
            "s3:PutObject"
          ]
          # バケットとその中のオブジェクトに対する操作
          Resource = [
            "arn:aws:s3:::power-forecasting-mlops-${terraform.workspace}",
            "arn:aws:s3:::power-forecasting-mlops-${terraform.workspace}/*"
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "ecr:GetAuthorizationToken",
            "ecr:BatchCheckLayerAvailability",
            "ecr:GetDownloadUrlForLayer",
            "ecr:BatchGetImage"
          ]
          Resource = "*"
        }
      ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "power_forecasting_policy_attachment" {
  role       = aws_iam_role.power_forecasting_role.name
  policy_arn = aws_iam_policy.power_forecasting_policy.arn
}

data "aws_iam_role" "studio_execution" {
  name = "AmazonSageMaker-ExecutionRole-20250507T172311"
}

resource "aws_iam_policy" "scopedown_ecr_access" {
  name = "scopedown-ecr-access"
  path = "/service-role/"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "scopedown_attach_ecr_access" {
  role       = data.aws_iam_role.studio_execution.name
  policy_arn = aws_iam_policy.scopedown_ecr_access.arn
}

resource "aws_iam_role_policy_attachment" "studio_attach_forecasting_policy" {
  role       = data.aws_iam_role.studio_execution.name
  policy_arn = aws_iam_policy.power_forecasting_policy.arn
}
