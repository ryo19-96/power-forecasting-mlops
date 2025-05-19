# noqa: INP001
import os
from typing import Dict

import boto3

ENV = os.environ.get("ENV", "dev")
sagemaker_client = boto3.client("sagemaker")
ssm_client = boto3.client("ssm")


def lambda_handler(event, _) -> Dict[str, str]:
    exec_arn = event["detail"]["PipelineExecutionArn"]

    # pipeline実行のパラメータから、保存したい"ModelPackageArn"、"EndpointName"を取得
    response = sagemaker_client.describe_pipeline_execution(PipelineExecutionArn=exec_arn)
    parameters = {i["Name"]: i["Value"] for i in response["PipelineParameters"]}

    arn = parameters["ModelPackageArn"]
    endpoint = parameters["EndpointName"]

    # 結果の保存
    ssm_client.put_parameter(
        Description="Latest deployed model package ARN",
        Name=f"/power-forecasting/{ENV}/sagemaker/deploy/last_deployed",
        Value=arn,
        Type="String",
        Overwrite=True,
    )
    ssm_client.put_parameter(
        Description="Current endpoint name",
        Name=f"/power-forecasting/{ENV}/sagemaker/deploy/current_endpoint",
        Value=endpoint,
        Type="String",
        Overwrite=True,
    )

    return {"status": "Parameter updated"}
