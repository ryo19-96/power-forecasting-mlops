import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import boto3
import yaml

from model_pipeline import get_pipeline

run_time = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d-%H%M%S")

config_path = Path(__file__).parent.parent / "config.yaml"
with Path(config_path).open("r") as f:
    config = yaml.safe_load(f)
run_config = config.get("run", {})
pipeline_config = config.get("pipeline", {})

region = run_config.get("region", "ap-northeast-1")
role = run_config.get("role")
default_bucket = run_config.get("default_bucket")
pipeline_name = run_config.get("pipeline_name", "PowerForecastPipeline")
environment = run_config.get("environment", "dev")
enable_cache = run_config.get("enable_cache", False)

sagemaker_client = boto3.client("sagemaker")
desc = sagemaker_client.describe_feature_group(FeatureGroupName="power_forecast_features")

glue_db = desc["OfflineStoreConfig"]["DataCatalogConfig"]["Database"]
glue_table = desc["OfflineStoreConfig"]["DataCatalogConfig"]["TableName"]

pipeline = get_pipeline(
    region=region,
    role=role,
    default_bucket=default_bucket,
    pipeline_name=pipeline_name,
    environment=environment,
    pipeline_config=pipeline_config,
    enable_cache=enable_cache,
)

# 定義をSageMakerに登録
pipeline.upsert(role_arn=role)

# 実行
execution = pipeline.start(
    execution_display_name=f"model-pipeline-{run_time}",
    parameters={
        "glue_db": glue_db,
        "glue_table": glue_table,
    },
)
print("Started pipeline execution:")
print(f"Execution ARN: {execution.arn}")

# actionsで完了を補足するために待機（GitHub Actions 環境でだけwaitさせる）
if os.getenv("CI") == "true":
    execution.wait()
    # 正常終了かチェック
    status = execution.describe()["PipelineExecutionStatus"]
    if status != "Succeeded":
        msg = f"Pipeline failed: {status}"
        raise RuntimeError(msg)
    else:
        print("Pipeline execution succeeded.")
