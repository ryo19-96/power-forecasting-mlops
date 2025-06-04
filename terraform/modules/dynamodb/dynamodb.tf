resource "aws_dynamodb_table" "watermark" {
  name         = "watermark-${terraform.workspace}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_name"

  attribute {
    name = "job_name"
    type = "S"
  }
}
