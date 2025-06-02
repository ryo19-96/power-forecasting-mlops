resource "aws_iam_role" "emr_etl_exec" {
  name = "emr_etl_exec"
  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "AllowS3Access",
        "Effect" : "Allow",
        "Action" : [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ],
        "Resource" : [
          "arn:aws:s3:::your-raw-bucket-name/*",
          "arn:aws:s3:::your-processed-bucket-name/*"
        ]
      },
      {
        "Sid" : "AllowCloudWatchLogs",
        "Effect" : "Allow",
        "Action" : [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        "Resource" : "*"
      }
    ]
  })
}

resource "aws_iam_policy_attachment" "emr_etl_exec_policy" {
  name       = "emr-etl-exec-policy-attachment"
  roles      = [aws_iam_role.emr_etl_exec.name]
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

output "emr_etl_exec_role" {
  value = aws_iam_role.emr_etl_exec
}
