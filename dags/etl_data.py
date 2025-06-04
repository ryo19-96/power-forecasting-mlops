import argparse
import io
import os
from typing import List

import boto3
import pandas as pd
from pyspark.sql import SparkSession, functions
from pyspark.sql.functions import col

# zipfileの展開先バケット
RAW_BUCKET = os.getenv("RAW_BUCKET", "power-forecasting-extract-data-dev")
# 処理済みデータの保存先バケット
PROCESSED_BUCKET = os.getenv("PROCESSED_BUCKET", "power-forecasting-processed-data-dev")

spark = SparkSession.builder.appName("ETLPowerWeather_Data").getOrCreate()
s3_client = boto3.client("s3")


def parse_arguments() -> argparse.Namespace:
    """
    コマンドライン引数をパースする
    --dates: カンマ区切りの日付文字列（例: "2023-01-01,2023-01-02"）

    Returns:
        argparse.Namespace: パースされた引数
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", type=str, required=True, help="Comma-separated dates (YYYY-MM-DD)")
    return parser.parse_args()


def read_power_usage_data(date_str: str) -> pd.DataFrame:
    """
    指定された日付の電力使用量データを読み込み、最大電力を抽出して整形したDataFrameを返す

    Args:
        date_str (str): 対象の日付（YYYY-MM-DD形式）

    Returns:
        pd.DataFrame: 最大電力使用量データのDataFrame

    Raises:
        RuntimeError: データの読み込みに失敗した場合
    """
    yyyymm = "-".join(date_str.split("-")[:2])  # YYYY-MM形式に変換
    key = f"raw_power_usage/{yyyymm}/{date_str}/power_usage.csv"
    try:
        body = s3_client.get_object(Bucket=RAW_BUCKET, Key=key)["Body"].read()
        df = pd.read_csv(io.BytesIO(body), encoding="shift-jis", skiprows=54)
        max_power = int(df["当日実績(５分間隔値)(万kW)"].max())
        data = {"date": date_str, "max_power": max_power}
    except s3_client.exceptions.NoSuchKey as e:
        msg = f"Power usage data not found for {date_str}"
        raise RuntimeError(msg) from e
    return pd.DataFrame([data])


def read_weather_data(date_str: str) -> pd.DataFrame:
    """
    指定された日付の気象データを読み込み、対象のカラムのみを抽出して整形したDataFrameを返す
    Args:
        date_str (str): 対象の日付（YYYY-MM-DD形式）

    Returns:
        pd.DataFrame: 整形後の気象データのDataFrame

    Raises:
        RuntimeError: データの読み込みに失敗した場合"""
    yyyymm = "-".join(date_str.split("-")[:2])  # YYYY-MM形式に変換
    key = f"raw_weather_data/{yyyymm}/{date_str}/weather_data.csv"
    try:
        body = s3_client.get_object(Bucket=RAW_BUCKET, Key=key)["Body"].read()
        df = pd.read_csv(io.BytesIO(body))
        df = df[["date", "最高気温(℃)", "最低気温(℃)", "天気概況(昼：06時〜18時)"]].rename(
            columns={
                "date": "date",
                "最高気温(℃)": "max_temp",
                "最低気温(℃)": "min_temp",
                "天気概況(昼：06時〜18時)": "weather",
            },
        )
    except s3_client.exceptions.NoSuchKey as e:
        msg = f"Weather data not found for {date_str}"
        raise RuntimeError(msg) from e
    return df


def main(dates: List[str]) -> None:
    """
    メイン処理
    引数で指定された日付の範囲に対して、気象データと電力使用量データを結合し、S3に保存する

    Args:
        args (argparse.Namespace): コマンドライン引数
    """
    power_dfs = []
    weather_dfs = []

    for d in dates:
        power_data = read_power_usage_data(d)
        weather_data = read_weather_data(d)

        if power_data is not None and weather_data is not None:
            power_dfs.append(power_data)
            weather_dfs.append(weather_data)

    power_df = spark.createDataFrame(pd.concat(power_dfs).astype({"date": "str"})).withColumn(
        "date",
        functions.to_date("date", "yyyy-MM-dd"),
    )
    power_df = power_df.repartition("date")

    weather_df = spark.createDataFrame(pd.concat(weather_dfs).astype({"date": "str"})).withColumn(
        "date",
        functions.to_date("date", "yyyy-MM-dd"),
    )
    weather_df = weather_df.repartition("date")

    # データの結合
    merged_df = weather_df.join(
        power_df,
        on=["date"],
        how="inner",
    )
    merged_df = merged_df.withColumn("dt", col("date"))
    # データの保存
    merged_df.write.mode("overwrite").partitionBy("dt").parquet(f"s3://{PROCESSED_BUCKET}/dt_tmp/")


if __name__ == "__main__":
    args = parse_arguments()
    dates = [d.strip() for d in args.dates.split(",")]
    main(dates)
