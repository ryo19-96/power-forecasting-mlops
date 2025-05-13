import sys
from pathlib import Path

import sagemaker
from pipeline_aws import get_pipeline
import sagemaker.session

region = "ap-northeast-1"
role = "arn:aws:iam::163817410757:role/service-role/AmazonSageMaker-ExecutionRole-20250507T172311"
default_bucket = "power-forecasting-mlops-dev"
pipeline_name = "PowerForecastPipeline"

pipeline = get_pipeline(
    region=region,
    role=role,
    default_bucket=default_bucket,
    pipeline_name=pipeline_name,
    environment="dev",
)

# 1. 定義をSageMakerに登録（なければ作成・あれば更新）
pipeline.upsert(role_arn=role)

# 2. パラメータ（任意）を渡して実行
execution = pipeline.start()
print("Started pipeline execution:")
print(f"Execution ARN: {execution.arn}")
