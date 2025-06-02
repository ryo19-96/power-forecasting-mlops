import datetime
import io
import json
import os
import re
from typing import Iterator, List

import boto3

RAW_BUCKET = os.environ.get("RAW_BUCKET", "power-forecasting-extract-data-dev")
WATERMARK_KEY = os.environ.get("WATERMARK_KEY", "system/watermark.json")

s3_client = boto3.client("s3")


def check_watermark_dates() -> str:
    """
    S3バケットからウォーターマークファイルを取得し、処理済みの日付を確認する。

    Returns:
        str: 処理された最後の日付（YYYY-MM-DD形式）。ウォーターマークファイルが存在しない場合は1970-01-01を返す

    Raises:
        FileNotFoundError: ウォーターマークファイルが存在しない場合に発生
    """
    try:
        s3_object = s3_client.get_object(Bucket=RAW_BUCKET, Key=WATERMARK_KEY)
        watermark_data = json.load(io.BytesIO(s3_object["Body"].read()))
        return watermark_data.get("last_processed", "1970-01-01")
    except s3_client.exceptions.NoSuchKey:
        msg = f"Watermark file {WATERMARK_KEY} does not exist in bucket {RAW_BUCKET}."
        raise FileNotFoundError(msg)


def list_unprocessed_dates() -> List[str]:
    """
    EMRの処理対象として使用する日付を抽出する関数
    S3バケット内のraw_power_usageとraw_weather_dataディレクトリから日付をリストを抽出し、
    ウォーターマークで処理された最後の処理日より新しい日付を返す

    Returns:
        list: 未処理の日付のリスト（YYYY-MM-DD形式）
    """
    last_date = check_watermark_dates()
    last_dt = datetime.datetime.strptime(last_date, "%Y-%m-%d").date()  # noqa: DTZ007

    def dates_under(prefix) -> Iterator[str]:
        # 指定されたプレフィックスの下にある日付をリストするジェネレータ
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=RAW_BUCKET, Prefix=prefix)
        print(f"Months under {prefix}: {page_iterator}")
        for page in page_iterator:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                match = re.compile(r"\d{4}-\d{2}-\d{2}").search(key)
                if match:
                    yield match.group()

    power_usage_dates = set(dates_under("raw_power_usage/"))
    weather_dates = set(dates_under("raw_weather_data/"))

    # 両方に存在 & last_dt より新しい日
    unprocessed_dates = sorted(
        date
        for date in (power_usage_dates & weather_dates)
        if datetime.datetime.strptime(date, "%Y-%m-%d").date() > last_dt  # noqa: DTZ007
    )
    return unprocessed_dates


def check_unprocessed_dates(**context) -> List[str]:
    """
    未処理の日付をチェックし、XComに格納する
    Args:
        context (dict): Airflowのコンテキスト

    Returns:
        List[str]: 未処理の日付のリスト（YYYY-MM-DD形式）
    """
    targets = list_unprocessed_dates()
    # XComに格納
    context["ti"].xcom_push(key="targets", value=targets)
    print(f"Unprocessed dates: {targets}")
    return targets


def decide_to_run_emr(**context) -> str:
    """
    EMRジョブを実行するかどうかを決定する関数
    未処理の日付がある場合はEMRジョブを実行し、ない場合はスキップする

    Args:
        context (dict): Airflowのコンテキスト
    Returns:
        str: 次に実行するタスク名
    """
    targets = context["ti"].xcom_pull(task_ids="check_unprocessed_dates_op", key="targets")
    if targets:
        return "run_emr_job"
    return "skip_etl"
