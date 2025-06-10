import subprocess
import sys

# 必要なパッケージをその場でインストール
subprocess.run(
    [sys.executable, "-m", "pip", "install", "--quiet", "sagemaker"],
    check=True,
)

import argparse
import datetime
import logging
from pathlib import Path

import boto3
import pandas as pd
from sagemaker.feature_store.feature_group import FeatureGroup
from sagemaker.session import Session

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def parse_args() -> argparse.Namespace:
    """SageMakerから渡される引数をパースする

    Returns:
        argparse.Namespace: パースされた引数
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-group-name", type=str)
    parser.add_argument("--region", type=str, default="ap-northeast-1")
    return parser.parse_args()


if __name__ == "__main__":
    logger.info("Starting feature store ingestion...")
    args = parse_args()
    boto_session = boto3.Session(region_name=args.region)
    session = Session(boto_session=boto_session)
    feature_group = FeatureGroup(name=args.feature_group_name, sagemaker_session=session)

    #  前ステップから渡された特徴量（parquet形式）を読み込み
    df = pd.read_parquet("/opt/ml/processing/extract_features/")

    # Feature Store に必須の列（record_identifier, event_time）を追加
    #    - record_id: 一意のID
    #    - event_time: 時系列順序を定義
    df["record_id"] = df["date"].astype(str)
    df["event_time"] = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: UP017

    feature_group.ingest(
        data_frame=df,
        max_workers=4,
        wait=True,
    )
    # オフラインストアのメタデータを取得し、URIを保存
    offline_uri = feature_group.describe()["OfflineStoreConfig"]["S3StorageConfig"]["S3Uri"]
    logger.info(f"Offline store URI: {offline_uri}")
    Path("/opt/ml/processing/offline_uri/uri.txt").write_text(offline_uri)

    logger.info("Feature store ingestion completed successfully.")
