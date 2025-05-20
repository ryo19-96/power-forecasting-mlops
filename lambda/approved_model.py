# noqa: INP001
import os
import urllib.parse
from typing import Any, Dict

import boto3

ROLE = os.environ["SAGEMAKER_ROLE"]
ENV = os.environ.get("ENV", "dev")
PIPELINE_NAME = os.environ["DEPLOY_PIPELINE"]

endpoint_name = f"power-forecast-serverless-{ENV}"


def lambda_handler(event: Dict[str, Any], _) -> None:
    """
    メールでapprovedされたら実行（呼び出し元はAPI Gateway）
    approvedモデル情報をParameter Store に保存 → deployment_pipeline発火（既に同じモデルがデプロイされていればskip）

    Args:
        event (dict): Lambda関数に渡されるイベント
        context: Lambdaのコンテキスト情報（使用しない）
    """
    params = event.get("queryStringParameters", {})
    package_arn = urllib.parse.unquote(params.get("pkg", ""))
    if not package_arn:
        return {"statusCode": 400, "body": "Missing parameters"}

    sagemaker_client = boto3.client("sagemaker")
    ssm_client = boto3.client("ssm")

    # モデルを"approved"に更新
    sagemaker_client.update_model_package(
        ModelPackageArn=package_arn,
        ModelApprovalStatus="Approved",
    )
    # "approve"に更新したARNをParameter Storeに保存
    ssm_client.put_parameter(
        Description="Approved model package ARN",
        Name=f"/power-forecasting/{ENV}/sagemaker/model-registry/approved",
        Value=package_arn,
        Type="String",
        Overwrite=True,
    )

    # モデルのデプロイ（既に同じモデルがデプロイされていればskip）
    try:
        prev = ssm_client.get_parameter(Name=f"/power-forecasting/{ENV}/sagemaker/deploy/last_deployed")["Parameter"][
            "Value"
        ]
    except Exception:
        prev = None

    if prev == package_arn:
        return {"statusCode": 200, "body": "Model already deployed. Skipping deployment."}

    # deployment_pipelineを実行
    sagemaker_client.start_pipeline_execution(
        PipelineName=PIPELINE_NAME,
        PipelineParameters=[
            {"Name": "ModelPackageArn", "Value": package_arn},
            {"Name": "EndpointName", "Value": endpoint_name},
        ],
    )
    # ブラウザに結果をHTMLで表示する
    status = "Approved"
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": f"<h3>{status} model</h3><p>{package_arn}</p>",
    }
