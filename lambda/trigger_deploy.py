# noqa: INP001
import os
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

import boto3

sagemake_client = boto3.client("sagemaker")
PIPELINE_NAME = os.environ["DEPLOY_PIPELINE"]
ROLE_ARN = os.environ["PIPELINE_EXEC_ROLE"]

# エンドポイント名は日本時間のタイムスタンプを付与
jst_now = datetime.now(ZoneInfo("Asia/Tokyo"))
timestamp_str = jst_now.strftime("%Y%m%d-%H%M%S")
endpoint_name = f"power-forecast-serverless-{timestamp_str}"


def lambda_handler(event, _) -> Dict[str, Any]:
    package_arn = event["detail"]["ModelPackageArn"]

    response = sagemake_client.start_pipeline_execution(
        PipelineName=PIPELINE_NAME,
        PipelineParameters=[
            {"Name": "ModelPackageArn", "Value": package_arn},
            {"Name": "EndpointName", "Value": endpoint_name},
        ],
    )
    return {"execution_arn": response["PipelineExecutionArn"]}
