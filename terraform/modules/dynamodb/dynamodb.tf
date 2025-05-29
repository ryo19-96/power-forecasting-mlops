resource "aws_dynamodb_table" "watermark" {
  name         = "watermark-${terraform.workspace}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  # パーティションキー（power, weather, etc.を想定）
  attribute {
    name = "pk"
    type = "S"
  }
  # ソートキー（日付を想定）
  attribute {
    name = "sk"
    type = "S"
  }
}
