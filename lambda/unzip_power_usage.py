# noqa: INP001
import io
import logging
import os
import zipfile

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")

BUCKET = os.environ["BUCKET"]


def lambda_handler(event, _) -> None:
    """
    S3バケットからZIPファイルを展開してファイルが展開先に存在していなければ
    raw_power_usageディレクトリに保存するLambda関数

    Args:
        event (dict): Lambda関数に渡されるイベント
    """
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    zip_key = event["Records"][0]["s3"]["object"]["key"]

    logger.info(f"Processing ZIP file: {zip_key} from bucket: {bucket}")

    zip_object = s3_client.get_object(Bucket=bucket, Key=zip_key)
    zip_content = zip_object["Body"].read()
    zip_buffer = io.BytesIO(zip_content)

    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        for filename in zip_file.namelist():
            # e.g. 20221210_power_usage.csv
            date_str = filename.split("_")[0]
            year_month = f"{date_str[:4]}-{date_str[4:6]}"
            date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            key = f"raw_power_usage/{year_month}/{date_fmt}/power_usage.csv"

            # すでに存在するか確認
            try:
                s3_client.head_object(Bucket=BUCKET, Key=key)
                logger.info(f"{key} already exists. skipping.")
                continue
            except s3_client.exceptions.ClientError as e:
                if e.response["Error"]["Code"] != "404":
                    raise

            # 存在しなければ保存
            content = zip_file.read(filename)
            s3_client.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=content,
            )
