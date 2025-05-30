resource "aws_emrserverless_application" "etl" {
  name          = "power_weather_etl"
  release_label = "emr-6.15.0"
  type          = "spark"

  maximum_capacity {
    cpu    = "2 vCPU"
    memory = "10 GB"
  }
}
