import datetime
import os
import re
from typing import Iterator, List

import boto3

RAW_BUCKET = os.environ.get("RAW_BUCKET", "power-forecasting-extract-data-dev")

table = boto3.resource("dynamodb").Table("watermark-dev")
s3_client = boto3.client("s3")


def get_watermark(job: str = "etl_data") -> str:
    """
    dynamoDBから最後に処理された日付を取得する

    Args:
        job (str): ジョブ名。デフォルトは"etl_data"

    Returns:
        str: 最後に処理された日付（YYYY-MM-DD形式）。存在しない場合は"2022-01-01"を返す
    """
    item = table.get_item(Key={"job_name": job}).get("Item")
    return item["last_processed"] if item else "2022-01-01"


def list_unprocessed_dates() -> List[str]:
    """
    EMRの処理対象として使用する日付を抽出する関数
    S3バケット内のraw_power_usageとraw_weather_dataディレクトリから日付をリストを抽出し、
    ウォーターマークで処理された最後の処理日より新しい日付を返す

    Returns:
        list: 未処理の日付のリスト（YYYY-MM-DD形式）
    """
    last_date = get_watermark()
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
