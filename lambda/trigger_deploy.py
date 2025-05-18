# noqa: INP001
import logging
import os
from typing import Any, Dict

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


sagemaker_client = boto3.client("sagemaker")
# AWS Systems Manager パラメーターストアに保存するためのクライアント
ssm_client = boto3.client("ssm")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, str]:
    """Approvedになったモデルをトリガーにしてデプロイ処理を実行するラムダ関数
    Args:
        event (Dict[str, Any]): イベントトリガー情報
        context (Any): 実行コンテキスト情報（関数名やメモリなど）
    Returns:
        Dict[str, str]: レスポンス情報
    """
    logger.info("=== Lambda Triggered ===")
    logger.info("Event detail:", event.get("detail", {}))
    logger.info("event =", event)
    logger.info("context =", vars(context))
    # どの ModelPackage が approved になったかを取得
    pkg_arn = event["detail"]["ModelPackageArn"]

    # (オプション) ApprovedモデルをParameterStoreに保存
    ssm_client.put_parameter(Name="/mlops/pf/dev/approved", Value=pkg_arn, Type="String", Overwrite=True)

    # パイプラインを起動
    sagemaker_client.start_pipeline_execution(
        PipelineName=os.environ["PIPELINE_NAME"],
        RoleArn=os.environ["PIPELINE_ROLE_ARN"],
        PipelineParameters=[{"Name": "ModelPackageArn", "Value": pkg_arn}],
    )

    return {"status": "started", "model_package": pkg_arn}
