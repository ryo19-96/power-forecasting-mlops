variable "account_id" {
  type = string
}

# sagemaker の使用ロール
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
  name = "power-forecasting-role-${terraform.workspace}"
  path = "/service-role/"
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

# ロールの ARN を出力
output "power_forecasting_role_arn" {
  value = aws_iam_role.power_forecasting_role.arn
}

resource "aws_iam_policy" "power_forecasting_policy" {
  name = "power-forecasting-${terraform.workspace}"
  path = "/service-role/"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ],
        Resource = [
          "arn:aws:s3:::power-forecasting-mlops-${terraform.workspace}",
          "arn:aws:s3:::power-forecasting-mlops-${terraform.workspace}/*",
          "arn:aws:s3:::power-forecasting-processed-data-${terraform.workspace}",
          "arn:aws:s3:::power-forecasting-processed-data-${terraform.workspace}/*",
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "cloudwatch:PutMetricData"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        # TODO: 最小権限にする
        Action = [
          "sagemaker:*"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Resource = [
          "arn:aws:s3:::jumpstart-cache-prod-ap-northeast-1",
          "arn:aws:s3:::jumpstart-cache-prod-ap-northeast-1/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "glue:CreateTable",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetDatabase",
          "glue:DeleteTable",
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:GetBucketAcl", "s3:GetBucketLocation"],
        Resource = [
          "arn:aws:s3:::power-forecast-featurestore-offline-${terraform.workspace}",
          "arn:aws:s3:::power-forecast-featurestore-offline-${terraform.workspace}/*",
          "arn:aws:s3:::power-forecast-athena-query-results-${terraform.workspace}",
          "arn:aws:s3:::power-forecast-athena-query-results-${terraform.workspace}/*",
        ]
      },
      {
        Effect   = "Allow",
        Action   = ["sagemaker:PutRecord", "sagemaker:BatchGetRecord"],
        Resource = "*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "athena:GetWorkGroup",
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults"
        ],
        "Resource" : "*"
      }
    ]
  })
}
resource "aws_iam_role_policy_attachment" "power_forecasting_role_policy_attachment" {
  role       = aws_iam_role.power_forecasting_role.name
  policy_arn = aws_iam_policy.power_forecasting_policy.arn
}

resource "aws_iam_policy" "sagemaker_logs" {
  name = "sagemaker-cloudwatch-logs"
  path = "/service-role/"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ],
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_logs" {
  role       = aws_iam_role.power_forecasting_role.name
  policy_arn = aws_iam_policy.sagemaker_logs.arn
}
