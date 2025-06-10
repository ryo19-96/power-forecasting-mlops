resource "aws_iam_role" "sagemaker_featurestore_role" {
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
  name = "power-forecast-featurestore-role-${terraform.workspace}"
  path = "/service-role/"
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}

resource "aws_iam_policy" "sagemaker_featurestore_policy" {
  name = "power-forecast-featurestore-policy-${terraform.workspace}"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
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
        Effect = "Allow",
        Action = [
          "glue:CreateTable",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetDatabase",
          "glue:DeleteTable",
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_feature_store" {
  role       = aws_iam_role.sagemaker_featurestore_role.name
  policy_arn = aws_iam_policy.sagemaker_featurestore_policy.arn
}

output "sagemaker_featurestore_role_arn" {
  value = aws_iam_role.sagemaker_featurestore_role.arn
}
