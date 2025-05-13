resource "aws_iam_policy" "notebook_permissions" {
  name = "notebook-access-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:PassRole"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::sagemaker-*",
          "arn:aws:s3:::sagemaker-*/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_notebook_permissions" {
  role       = aws_iam_role.power_forecasting_role.name
  policy_arn = aws_iam_policy.notebook_permissions.arn
}
