import os
import time
import datetime
import logging
import boto3
from typing import Tuple, Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PIPELINE_NAME = os.environ.get("PIPELINE_NAME", "PowerForecastPipeline")
FEATURE_GROUP_NAME = os.environ.get("FEATURE_GROUP_NAME")
logger.info(f"PIPELINE_NAME: {PIPELINE_NAME}, FEATURE_GROUP_NAME: {FEATURE_GROUP_NAME}")

sagemaker_client = boto3.client("sagemaker")

now_jst = datetime.datetime.fromtimestamp(time.time(), tz=datetime.timezone(datetime.timedelta(hours=9))).strftime(
    "%Y%m%d-%H%M%S",
)


def _get_glue_params(feature_group_name: str) -> Tuple[str, str]:
    """Feature Group を describe して Glue DB / Table 名を取得

    Args:
        feature_group_name (str): SageMaker Feature Group の名前

    Returns:
        Tuple[str, str]: Glue データベース名とテーブル名
    """
    desc = sagemaker_client.describe_feature_group(FeatureGroupName=feature_group_name)
    cfg = desc["OfflineStoreConfig"]["DataCatalogConfig"]
    return cfg["Database"], cfg["TableName"]


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, str]:
    """EventBridge Scheduler からのイベントを受けて SageMaker Pipeline を実行する Lambda 関数

    Args:
        event (Dict[str, Any]): イベントトリガー情報
        context (Any): 実行コンテキスト情報（関数名やメモリなど）

    Returns:
        Dict[str, str]: 実行されたパイプラインのARN
    """
    parameters = []
    if FEATURE_GROUP_NAME:
        db, tbl = _get_glue_params(FEATURE_GROUP_NAME)
        parameters = [
            {"Name": "glue_db", "Value": db},
            {"Name": "glue_table", "Value": tbl},
        ]
        logger.info(f"Glue params: db={db}, table={tbl}")

    response = sagemaker_client.start_pipeline_execution(
        PipelineName=PIPELINE_NAME,
        PipelineExecutionDisplayName=f"scheduled-{now_jst}",
        PipelineParameters=parameters,
    )
    arn = response["PipelineExecutionArn"]
    logger.info(f"Started execution: {arn}")
    return {"pipelineExecutionArn": arn}
