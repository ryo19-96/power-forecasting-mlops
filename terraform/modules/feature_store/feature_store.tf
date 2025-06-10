variable "offline_bucket" {
  type = string
}
variable "sagemaker_featurestore_role_arn" {
  type = string
}

resource "aws_glue_catalog_database" "feature_db" {
  name = "power_features_db"
}

resource "aws_glue_catalog_table" "feature_table" {
  name          = "power_forecast_features"
  database_name = aws_glue_catalog_database.feature_db.name
  table_type    = "EXTERNAL_TABLE"

  storage_descriptor {
    location      = "s3://${var.offline_bucket}/163817410757/sagemaker/ap-northeast-1/offline-store/power_forecast_features-1749474799/data"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "record_id"
      type = "string"
    }
    columns {
      name = "event_time"
      type = "string"
    }

    columns {
      name = "date"
      type = "string"
    }
    columns {
      name = "weather_category"
      type = "string"
    }
    columns {
      name = "max_temp"
      type = "double"
    }
    columns {
      name = "min_temp"
      type = "double"
    }
    columns {
      name = "max_power"
      type = "bigint"
    }
    columns {
      name = "avg"
      type = "double"
    }
    columns {
      name = "rng"
      type = "double"
    }
    columns {
      name = "cdd"
      type = "double"
    }
    columns {
      name = "hdd"
      type = "double"
    }
    columns {
      name = "hot"
      type = "int"
    }
    columns {
      name = "cold"
      type = "int"
    }
    columns {
      name = "year"
      type = "int"
    }
    columns {
      name = "month"
      type = "int"
    }
    columns {
      name = "day"
      type = "int"
    }
    columns {
      name = "dow"
      type = "int"
    }
    columns {
      name = "dow_sin"
      type = "double"
    }
    columns {
      name = "dow_cos"
      type = "double"
    }
    columns {
      name = "mon_sin"
      type = "double"
    }
    columns {
      name = "mon_cos"
      type = "double"
    }
    columns {
      name = "weekend"
      type = "int"
    }
    columns {
      name = "holiday"
      type = "int"
    }
  }

  parameters = {
    "classification" = "parquet"
    "typeOfData"     = "file"
  }

  depends_on = [
    aws_sagemaker_feature_group.power_features
  ]
}

resource "aws_sagemaker_feature_group" "power_features" {
  feature_group_name             = "power_forecast_features"
  record_identifier_feature_name = "record_id"
  event_time_feature_name        = "event_time"
  role_arn                       = var.sagemaker_featurestore_role_arn

  # ===== Feature 定義 =====
  feature_definition {
    feature_name = "record_id"
    feature_type = "String"
  }
  feature_definition {
    feature_name = "event_time"
    feature_type = "String"
  }
  feature_definition {
    feature_name = "date"
    feature_type = "String"
  }
  feature_definition {
    feature_name = "max_temp"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "min_temp"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "max_power"
    feature_type = "Integral"
  }
  feature_definition {
    feature_name = "weather_category"
    feature_type = "String"
  }
  feature_definition {
    feature_name = "avg"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "rng"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "cdd"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "hdd"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "hot"
    feature_type = "Integral"
  }
  feature_definition {
    feature_name = "cold"
    feature_type = "Integral"
  }
  feature_definition {
    feature_name = "year"
    feature_type = "Integral"
  }
  feature_definition {
    feature_name = "month"
    feature_type = "Integral"
  }
  feature_definition {
    feature_name = "day"
    feature_type = "Integral"
  }
  feature_definition {
    feature_name = "dow"
    feature_type = "Integral"
  }
  feature_definition {
    feature_name = "dow_sin"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "dow_cos"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "mon_sin"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "mon_cos"
    feature_type = "Fractional"
  }
  feature_definition {
    feature_name = "weekend"
    feature_type = "Integral"
  }
  feature_definition {
    feature_name = "holiday"
    feature_type = "Integral"
  }
  # ... 特徴量を追加したら足していく ...

  # ===== オフラインストア設定 =====
  offline_store_config {
    s3_storage_config {
      s3_uri = "s3://${var.offline_bucket}/"
    }
    data_catalog_config {
      catalog    = "AwsDataCatalog"
      database   = aws_glue_catalog_database.feature_db.name
      table_name = "power_forecast_features"
    }
    disable_glue_table_creation = true
  }
  tags = {
    Environment = terraform.workspace
    Project     = "PowerForecasting"
  }
}
