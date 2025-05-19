# noqa: INP001
import os
from typing import Any, Dict

import boto3

sagemake_client = boto3.client("sagemaker")
PIPELINE_NAME = os.environ["DEPLOY_PIPELINE"]
ROLE_ARN = os.environ["PIPELINE_EXEC_ROLE"]


def lambda_handler(event, _) -> Dict[str, Any]:
    package_arn = event["detail"]["ModelPackageArn"]

    response = sagemake_client.start_pipeline_execution(
        PipelineName=PIPELINE_NAME,
        PipelineParameters=[{"Name": "ModelPackageArn", "Value": package_arn}],
    )
    return {"execution_arn": response["PipelineExecutionArn"]}
