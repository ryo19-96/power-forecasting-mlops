# Lambda用IAMロール
resource "aws_iam_role" "lambda_email_role" {
  name = "lambda-email-role-${terraform.workspace}"
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

output "lambda_email_role" {
  value = aws_iam_role.lambda_email_role
}

resource "aws_iam_policy" "ses_send" {
  name = "AllowSESSend"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = [
        "ses:SendEmail",
        "ssm:PutParameter"
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
    }, ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_email_attach" {
  role       = aws_iam_role.lambda_email_role.name
  policy_arn = aws_iam_policy.ses_send.arn
}
