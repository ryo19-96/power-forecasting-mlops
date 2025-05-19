import os
import time

import boto3

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

    # ① SageMaker Model
    model_name = f"{endpoint_name}-{int(time.time())}"
    sagemaker_client.create_model(
        ModelName=model_name, ExecutionRoleArn=ROLE, Containers=[{"ModelPackageName": package_arn}],
    )

    # ② EndpointConfig（Serverless）
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

    # ③ Endpoint を upsert
    try:
        sagemaker_client.create_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name)
    except sagemaker_client.exceptions.ResourceInUse:
        sagemaker_client.update_endpoint(EndpointName=endpoint_name, EndpointConfigName=config_name)
