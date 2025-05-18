# noqa: INP001
import urllib.parse
from typing import Any, Dict

import boto3

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sagemaker_client = boto3.client("sagemaker")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """モデルを"Approved", "Rejected"に更新するラムダ関数
    API Gatewayが呼び出して、結果を返す。ブラウザが HTML としてレンダリングされる。

    Args:
        event (Dict[str, Any]): イベントトリガー情報
        context (Any): 実行コンテキスト情報（関数名やメモリなど）

    Returns:
        Dict[str, Any]: レスポンス情報
    """
    logger.info("=== Lambda Triggered ===")
    logger.info("Event detail:", event.get("detail", {}))
    logger.info("event =", event)
    logger.info("context =", vars(context))

    action = event["queryStringParameters"]["action"]
    model_package_arn = urllib.parse.unquote(event["queryStringParameters"]["pkg"])

    # 不正なURLなら 400 エラー返す
    if action not in {"approve", "reject"} or not model_package_arn:
        return {"statusCode": 400, "body": "Missing or invalid parameters"}

    # SageMaker Model Registry のモデルを承認 or 拒否に更新
    status = "Approved" if action == "approve" else "Rejected"
    sagemaker_client.update_model_package(
        ModelPackageArn=model_package_arn,
        ModelApprovalStatus=status,
    )
    # ブラウザに結果をHTMLで表示する
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": f"<h3>{status} model</h3><p>{model_package_arn}</p>",
    }
