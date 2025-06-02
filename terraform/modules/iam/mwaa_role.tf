resource "aws_iam_role" "mwaa_exec_role" {
  name = "mwaa_exec_role"

  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "S3Access",
        "Effect" : "Allow",
        "Action" : [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ],
        "Resource" : [
          "arn:aws:s3:::your-mwaa-dag-bucket-name",
          "arn:aws:s3:::your-mwaa-dag-bucket-name/*",
          "arn:aws:s3:::your-raw-bucket/*",
          "arn:aws:s3:::your-processed-bucket/*"
        ]
      },
      {
        "Sid" : "EMRServerlessAccess",
        "Effect" : "Allow",
        "Action" : [
          "emr-serverless:StartJobRun",
          "emr-serverless:GetJobRun",
          "emr-serverless:ListJobRuns"
        ],
        "Resource" : "*"
      },
      {
        "Sid" : "LogsAccess",
        "Effect" : "Allow",
        "Action" : [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        "Resource" : "*"
      },
      {
        "Sid" : "SSMAccess",
        "Effect" : "Allow",
        "Action" : [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ],
        "Resource" : "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "mwaa_exec_attachment" {
  role       = aws_iam_role.mwaa_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}
