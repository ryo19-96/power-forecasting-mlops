import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pipeline_aws import get_pipeline

run_time = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d-%H%M%S")

config_path = Path(__file__).parent / "config.yaml"
with Path(config_path).open("r") as f:
    config = yaml.safe_load(f)
run_config = config.get("run", {})

region = run_config.get("region", "ap-northeast-1")
role = run_config.get("role")
default_bucket = run_config.get("default_bucket")
pipeline_name = run_config.get("pipeline_name", "PowerForecastPipeline")
environment = run_config.get("environment", "dev")

pipeline = get_pipeline(
    region=region,
    role=role,
    default_bucket=default_bucket,
    pipeline_name=pipeline_name,
    environment=environment,
)

# 定義をSageMakerに登録
pipeline.upsert(role_arn=role)

# 実行
execution = pipeline.start(
    execution_display_name=f"model-pipeline-{run_time}",
)
print("Started pipeline execution:")
print(f"Execution ARN: {execution.arn}")

# actionsで完了を補足するために待機（GitHub Actions 環境でだけwaitさせる）
if os.getenv("CI") == "true":
    execution.wait()
    # 正常終了かチェック
    status = execution.describe()["PipelineExecutionStatus"]
    if status != "Succeeded":
        msg = f"Pipeline execution failed: {status}"
        raise RuntimeError(msg)
    else:
        print("Pipeline execution succeeded.")
