# noqa: INP001
import io
import logging
import os

import boto3
import pandas as pd

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")

BUCKET = os.environ["BUCKET"]


def lambda_handler(event, _) -> None:
    """weather_file.csv を読み取り、日別に分割して raw_weather_data/dt=YYYY-MM-DD/ に保存
    すでにある日付は skip するLambda関数

    Args:
        event (dict): Lambda関数に渡されるイベント
    """
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    csv_key = event["Records"][0]["s3"]["object"]["key"]

    logger.info(f"Processing CSV file: {csv_key} from bucket: {bucket}")

    response = s3_client.get_object(Bucket=bucket, Key=csv_key)
    content = response["Body"].read()
    df = pd.read_csv(io.BytesIO(content), encoding="shift-jis", skiprows=[0, 1, 2, 4, 5])
    # 日付をdatetime型に変換
    df["date"] = pd.to_datetime(df["年月日"], format="%Y/%m/%d", errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.drop(columns=["年月日"])

    for date in df["date"].unique():
        dt = pd.to_datetime(date, format="%Y-%m-%d")
        year_month = dt.strftime("%Y-%m")
        key = f"raw_weather_data/{year_month}/{date}/weather_data.csv"

        # すでに存在するか確認
        try:
            s3_client.head_object(Bucket=BUCKET, Key=key)
            logger.info(f"{key} already exists. skipping.")
            continue
        except s3_client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] != "404":
                raise

        # 存在しなければ保存
        buffer = io.StringIO()
        save_df = df[df["date"] == date]
        save_df.to_csv(buffer, index=False, encoding="shift-jis", errors="ignore")
        s3_client.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=buffer.getvalue(),
        )
        logger.info(f"Saved {key} to S3 bucket {BUCKET}")
