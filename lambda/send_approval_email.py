# noqa: INP001
import logging
import os
import urllib.parse
from typing import Any, Dict

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses = boto3.client("ses")


def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    """モデルの承認メールを送るラムダ関数
    Args:
        event (Dict[str, Any]): イベントトリガー情報
        context (Any): 実行コンテキスト情報（関数名やメモリなど）
    """
    logger.info("=== Lambda Triggered ===")
    logger.info("Event detail:", event.get("detail", {}))
    logger.info("event =", event)
    logger.info("context =", vars(context))
    approver_email = os.environ["APPROVER_EMAIL"]
    api_url = os.environ["API_URL"]

    model_package_arn = event["detail"]["ModelPackageArn"]
    approve_url = f"{api_url}?action=approve&pkg={urllib.parse.quote(model_package_arn)}"
    reject_url = f"{api_url}?action=reject&pkg={urllib.parse.quote(model_package_arn)}"

    ses.send_email(
        Source=approver_email,
        Destination={"ToAddresses": [approver_email]},
        Message={
            "Subject": {"Data": "model approval request"},
            "Body": {
                "Html": {
                    "Data": f"""
                        <p>New model registered</p>
                        <p><b>{model_package_arn}</b></p>
                        <p>
                            <a href="{approve_url}">✅ Approve</a> |
                            <a href="{reject_url}">❌ Reject</a>
                        </p>
                    """,
                },
            },
        },
    )
