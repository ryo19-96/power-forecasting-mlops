variable "pipeline_name" {
  type = string

}
variable "region" {
  type    = string
  default = "ap-northeast-1"
}

variable "account_id_lambda_pipeline_exec" {
  type = string
}

variable "feature_group_name" {
  type = string

}

resource "aws_iam_role" "lambda_pipeline_exec" {
  name = "lambda-start-${var.pipeline_name}-role"
  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17",
      Statement = [{
        Effect    = "Allow",
        Principal = { Service = ["lambda.amazonaws.com", "scheduler.amazonaws.com"] },
        Action    = "sts:AssumeRole"
        }
      ]
    }
  )
}

resource "aws_iam_policy" "lambda_sagemaker" {
  name = "lambda-start-${var.pipeline_name}-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = "sagemaker:StartPipelineExecution",
        Resource = "arn:aws:sagemaker:${var.region}:${var.account_id_lambda_pipeline_exec}:pipeline/${var.pipeline_name}"
      }
      ,
      {
        Effect : "Allow",
        Action : [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource : "*"
      },
      {
        Effect   = "Allow",
        Action   = "lambda:InvokeFunction",
        Resource = "*"
      },
      {
        Effect   = "Allow",
        Action   = "sagemaker:DescribeFeatureGroup",
        Resource = "arn:aws:sagemaker:${var.region}:${var.account_id_lambda_pipeline_exec}:feature-group/${var.feature_group_name}"
      }
    ]
    }
  )
}

resource "aws_iam_role_policy_attachment" "lambda_pipeline_exec_policy_attach" {
  role       = aws_iam_role.lambda_pipeline_exec.name
  policy_arn = aws_iam_policy.lambda_sagemaker.arn
}

output "lambda_pipeline_exec_role" {
  value = aws_iam_role.lambda_pipeline_exec
}
