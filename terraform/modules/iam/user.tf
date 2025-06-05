data "aws_iam_user" "me" {
  user_name = "watanabe"
}

resource "aws_iam_user_policy" "allow_mwaa_web" {
  name = "AllowMWAAWebLogin"
  user = data.aws_iam_user.me.user_name

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow"
      Action   = "airflow:WebLogin"
      Resource = "*"
    }]
  })
}

resource "aws_iam_user_policy" "allow_cost_view" {
  name = "AllowCostExplorerView"
  user = data.aws_iam_user.me.user_name

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "ce:GetUsageForecast",
          "ce:GetDimensionValues",
          "ce:GetReservationCoverage",
          "ce:GetReservationUtilization",
          "ce:GetRightsizingRecommendation",
          "ce:GetSavingsPlansCoverage",
          "ce:GetSavingsPlansUtilization",
          "ce:GetSavingsPlansUtilizationDetails",
          "ce:ListCostCategoryDefinitions"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "aws-portal:ViewBilling",
          "aws-portal:ViewUsage"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "cur:DescribeReportDefinitions"
        ],
        Resource = "*"
      }
    ]
  })
}
