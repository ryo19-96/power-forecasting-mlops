import os
import time

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("REGION", "ap-northeast-1")
ROLE = os.environ["DEPLOYMENT_ROLE"]

sagemaker_client = boto3.client("sagemaker", region_name=REGION)


def lambda_handler(event, _) -> None:
    """endpointをデプロイするLambda関数
    Args:
        event (dict): Lambda関数に渡されるイベント
        _: Lambda関数に渡されるコンテキスト（使用しない）

    Returns:
        None
    """

    package_arn = event["model_package_arn"]
    endpoint_name = event["endpoint_name"]
    memory_mb = event.get("memory_mb", 2048)
    max_conc = event.get("max_conc", 5)

    # モデルを作成
    # エンドポイントが使うmodel名
    model_name = f"{endpoint_name}-{int(time.time())}"
    sagemaker_client.create_model(
        ModelName=model_name,
        ExecutionRoleArn=ROLE,
        Containers=[{"ModelPackageName": package_arn}],
    )

    # エンドポイント設定
    config_name = f"{endpoint_name}-config-{int(time.time())}"
    sagemaker_client.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": model_name,
                "ServerlessConfig": {"MemorySizeInMB": memory_mb, "MaxConcurrency": max_conc},
            },
        ],
    )

    # エンドポイントを作成 or 更新
    try:
        sagemaker_client.create_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name)
    except ClientError as e:
        if "already existing endpoint" in e.response["Error"]["Message"]:
            # 既存ならupdate
            sagemaker_client.update_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name)
        else:
            raise
