# noqa: INP001
import os
from typing import Dict

import boto3

ENV = os.environ.get("ENV", "dev")
sagemaker_client = boto3.client("sagemaker")
ssm_client = boto3.client("ssm")


def lambda_handler(event, _) -> Dict[str, str]:
    # endpointの名前を取得
    detail = event["detail"]
    endpoint = detail["EndpointName"]

    # parameter storeの /approved を取得
    arn = ssm_client.get_parameter(Name=f"/power-forecasting/{ENV}/sagemaker/model-registry/approved")["Parameter"][
        "Value"
    ]

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
