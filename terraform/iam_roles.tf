resource "aws_iam_role" "power-forecasting-role" {
  assume_role_policy = jsonencode(
    {
      Statement = [
        {
          Action = "sts:AssumeRole"
          Effect = "Allow"
          Principal = {
            Service = [
              "sagemaker.amazonaws.com",
            ]
          }
        },
      ]
      Version = "2012-10-17"
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

resource "aws_iam_role_policy_attachment" "attach_s3_read_policy" {
  role       = aws_iam_role.power-forecasting-role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}
