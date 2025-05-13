import logging
import os
import zipfile
import argparse
import pathlib
import pandas as pd
from typing import List

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class DataLoader:
    """データ読み込みを担当するクラス"""

    def __init__(self, weather_data_path: str, power_usage_data_path: str) -> None:
        """
        Args:
            config: 設定情報の辞書
                - data_dir: データディレクトリのパス
                - weather_file: 気象データファイル名
                - power_usage_dir: 電力使用量データディレクトリ名
        """
        self.weather_file = weather_data_path
        self.power_usage_dir = power_usage_data_path

    def load_weather_data(self, encoding: str = "shift-jis", skiprows: List[int] = [0, 1, 2, 4, 5]) -> pd.DataFrame:
        """気象データファイルを読み込む

        Args:
            encoding: ファイルエンコーディング
            skiprows: スキップする行番号のリスト

        Returns:
            pd.DataFrame: 気象データフレーム
        """
        df = pd.read_csv(self.weather_file, encoding=encoding, skiprows=skiprows)

        # 必要なカラムだけ抽出
        df = df[["年月日", "最高気温(℃)", "最低気温(℃)", "天気概況(昼：06時〜18時)"]]

        # カラム名を英語に変更
        df = df.rename(
            columns={
                "年月日": "date",
                "最高気温(℃)": "max_temp",
                "最低気温(℃)": "min_temp",
                "天気概況(昼：06時〜18時)": "weather",
            },
        )

        # 日付をdatetime型に変換
        df["date"] = pd.to_datetime(df["date"], format="%Y/%m/%d")

        return df

    def load_power_usage_data(self) -> pd.DataFrame:
        """電力使用量データを読み込む

        Returns:
            pd.DataFrame: 電力使用量データフレーム
        """
        zip_dir = self.power_usage_dir
        result = []

        # ZIP内のCSVファイルからデータを読み込む
        for zip_name in sorted(os.listdir(zip_dir)):
            if not zip_name.endswith(".zip"):
                continue

            zip_path = os.path.join(zip_dir, zip_name)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for csv_filename in zip_ref.namelist():
                    if not csv_filename.endswith(".csv"):
                        continue

                    with zip_ref.open(csv_filename) as csv_file:
                        try:
                            df = pd.read_csv(csv_file, encoding="shift-jis", skiprows=54)
                            max_power = df["当日実績(５分間隔値)(万kW)"].max()
                            result.append({"date": csv_filename.split("_")[0], "max_power": max_power})
                        except Exception as e:
                            logger.info(f"Error reading {csv_filename}: {e}")

        # 結果をDataFrameに変換
        power_usage_df = pd.DataFrame(result)
        power_usage_df["date"] = pd.to_datetime(power_usage_df["date"], format="%Y%m%d")

        return power_usage_df

    def merge_data(self) -> pd.DataFrame:
        """気象データと電力使用量データを統合する

        Returns:
            pd.DataFrame: 統合されたデータフレーム
        """
        weather_df = self.load_weather_data()
        power_usage_df = self.load_power_usage_data()

        # dateカラムを使って両方のデータフレームを結合
        return weather_df.merge(power_usage_df, on="date", how="inner")

    def format_target_first(self, df: pd.DataFrame, target_col: str = "max_power") -> pd.DataFrame:
        """目的変数を明示的に最初のカラムに移動する
        Args:
            df: 入力データフレーム
            target_col: 目的変数のカラム名

        Returns:
            pd.DataFrame: 目的変数が最初のカラムに移動したデータフレーム

        Notes:
            awsのビルドインモデルを使用した場合先頭列に目的変数が必要なため列の順番を変更する
        """
        y = df.pop(target_col)
        return pd.concat([y, df], axis=1)


if __name__ == "__main__":
    logger.info("Starting load data...")

    parser = argparse.ArgumentParser()
    parser.add_argument("--weather-input-data", type=str)
    parser.add_argument("--power-usage-input-data", type=str)
    args = parser.parse_args()

    base_dir = "/opt/ml/processing"

    weather_input_data_path = args.weather_input_data
    power_usage_input_data_path = args.power_usage_input_data

    data_loader = DataLoader(
        weather_data_path=weather_input_data_path,
        power_usage_data_path=power_usage_input_data_path,
    )
    merged_data = data_loader.merge_data()

    pathlib.Path(f"{base_dir}/output").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(merged_data).to_pickle(f"{base_dir}/output/merged_data.pkl")
    logger.info("Finished loading data...")
