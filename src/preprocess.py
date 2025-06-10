import subprocess
import sys

# 必要なパッケージをその場でインストール
subprocess.run(
    [sys.executable, "-m", "pip", "install", "--quiet", "holidays", "omegaconf", "category-encoders"],
    check=True,
)
sys.path.append("/opt/ml/processing/deps")
import argparse
import logging
import os
from pathlib import Path

import holidays
import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf
from io import StringIO

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def parse_args() -> argparse.Namespace:
    """
    SageMakerから渡される引数をパースする

    Returns:
        argparse.Namespace: パースされた引数
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input-data",
        type=str,
        default=os.environ.get("SM_CHANNEL_INPUT", "/opt/ml/processing/input_data/"),
    )

    return parser.parse_args()


def load_emr_output(input_path: str) -> pd.DataFrame:
    """EMRの出力ファイルを読み込む
    mwaaでの前処理後は以下のような形式で保存されている
    dt=2022-04-01/part-00000-xxxx.snappy.parquet
    dt=2022-04-02/part-00000-xxxx.snappy.parquet
    ⋮

    Args:
        s3_dir: EMRの出力ファイルのパス

    Returns:
        pd.DataFrame: 読み込んだデータフレーム
    """
    file_paths = list(Path(input_path).rglob("*.parquet"))
    if not file_paths:
        msg = f"No parquet files found under {input_path}"
        raise ValueError(msg)

    dfs = [pd.read_parquet(path) for path in file_paths]
    logger.info(f"Loaded {len(dfs)} files from {input_path}")
    return_df = pd.concat(dfs, ignore_index=True)
    # dt列が追加されるので削除
    if "dt" in return_df.columns:
        return_df = return_df.drop(columns=["dt"])
    # 日付をdatetime型に変換
    return_df["date"] = pd.to_datetime(return_df["date"], format="%Y-%m-%d")
    buffer = StringIO()
    return_df.info(buf=buffer)
    logger.info(f"DataFrame info: {buffer.getvalue()}")
    logger.info(f"DataFrame start_date: {return_df['date'].min()}")
    logger.info(f"DataFrame end_date: {return_df['date'].max()}")
    return return_df


def load_config(config_path: str) -> DictConfig:
    """設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス

    Returns:
        DictConfig: 設定情報
    """
    config = DictConfig(OmegaConf.load(config_path))
    return config


class FeatureEngineering:
    """特徴量エンジニアリングを行うクラス"""

    def __init__(self, config: DictConfig = None) -> None:
        """
        Args:
            config (DictConfig): 設定情報（省略可能）
        """
        self.config = config
        self.jp_holidays = holidays.Japan()  # type: ignore[attr-defined]
        thresholds = self.config.get("feature_thresholds")
        self.hot_day_threshold = thresholds.get("hot_day")
        self.cold_day_threshold = thresholds.get("cold_day")
        self.cdd_base = thresholds.get("cdd_base")
        self.hdd_base = thresholds.get("hdd_base")

    def categorize_weather(self, weather_df: pd.DataFrame, weather_col: str = "weather") -> pd.DataFrame:
        """天気の文字列を基本的なカテゴリに分類する

        Args:
            weather_df: 天気列を含むデータフレーム
            weather_col: 天気列の名前

        Returns:
            pd.DataFrame: weather_category列が追加されたデータフレーム
        """
        df = weather_df.copy()

        df["weather_category"] = df[weather_col].apply(self._weather_check)

        # 元の天気列は不要なので削除
        df = df.drop(columns=[weather_col])

        return df

    def _weather_check(self, weather: str) -> str:
        """天気の文字列を基本的なカテゴリに分類する関数

        Args:
            weather: 元の天気の説明文字列

        Returns:
            str: 分類された天気カテゴリ
                快晴、晴れ、晴れ時々曇り、晴れ時々雨、曇り、曇り時々雨、雨、
                雷雨、晴れ（雷あり）、曇り（雷あり）、雷、霧・もや、その他、不明 (NaN値の場合)

        Notes:
            雪や雷は優先的に処理される
        """
        if pd.isna(weather):
            return "不明"

        # 雪系
        if any(keyword in weather for keyword in ["雪", "ゆき"]):
            return "雪"

        # 雷系
        if "雷" in weather:
            if any(keyword in weather for keyword in ["雨", "あめ"]):
                return "雷雨"
            if any(keyword in weather for keyword in ["晴", "日射"]):
                return "晴れ(雷あり)"
            if any(keyword in weather for keyword in ["曇", "くもり"]):
                return "曇り(雷あり)"
            return "雷"

        # 晴れ系
        if "快晴" in weather:
            return "快晴"
        if any(keyword in weather for keyword in ["晴", "日射"]):
            if any(keyword in weather for keyword in ["曇", "くもり"]):
                return "晴れ時々曇り"
            if any(keyword in weather for keyword in ["雨", "あめ", "雷"]):
                return "晴れ時々雨"
            return "晴れ"

        # 曇り系
        if any(keyword in weather for keyword in ["曇", "くもり"]):
            if any(keyword in weather for keyword in ["雨", "あめ"]):
                return "曇り時々雨"
            return "曇り"

        # 雨系
        if any(keyword in weather for keyword in ["雨", "あめ"]):
            return "雨"

        # その他
        return "その他"

    def create_numeric_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """数値系特徴量を作成する

        Args:
            df: max_temp, min_temp列を含むデータフレーム

        Returns:
            pd.DataFrame: 特徴量を追加したデータフレーム
        """
        result_df = df.copy()

        # 平均気温
        result_df["avg"] = (df["max_temp"] + df["min_temp"]) / 2

        # 気温の日較差（最高気温と最低気温の差）
        result_df["rng"] = df["max_temp"] - df["min_temp"]

        # 冷房度日：平均気温がcdd_baseを超えた分だけ冷房が必要と考える指標
        result_df["cdd"] = (result_df["avg"] - self.cdd_base).clip(lower=0)

        # 暖房度日：平均気温がhdd_base未満の場合、暖房が必要と考える指標
        result_df["hdd"] = (self.hdd_base - result_df["avg"]).clip(lower=0)

        # 猛暑日フラグ（最高気温がhot_day_threshold以上か）
        result_df["hot"] = (df["max_temp"] >= self.hot_day_threshold).astype(int)

        # 冬日フラグ（最低気温がcold_day_threshold以下か）
        result_df["cold"] = (df["min_temp"] <= self.cold_day_threshold).astype(int)

        return result_df

    def create_calendar_features(self, df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
        """カレンダー系特徴量を作成する

        Args:
            df: date列を含むデータフレーム
            date_col: 日付列の名前

        Returns:
            pd.DataFrame: カレンダー特徴量を追加したデータフレーム
        """
        result_df = df.copy()

        # 年、月、日
        result_df["year"] = df[date_col].dt.year
        result_df["month"] = df[date_col].dt.month
        result_df["day"] = df[date_col].dt.day

        # 曜日 (0-6: 月-日)
        result_df["dow"] = df[date_col].dt.weekday

        # 曜日の周期性をsin-cos変換で表現
        result_df["dow_sin"] = np.sin(2 * np.pi * result_df["dow"] / 7)
        result_df["dow_cos"] = np.cos(2 * np.pi * result_df["dow"] / 7)

        # 月の周期性をsin-cos変換で表現
        result_df["mon_sin"] = np.sin(2 * np.pi * result_df["month"] / 12)
        result_df["mon_cos"] = np.cos(2 * np.pi * result_df["month"] / 12)

        # 週末フラグ（土日か）
        result_df["weekend"] = (result_df["dow"] >= 5).astype(int)

        # 祝日フラグ
        result_df["holiday"] = result_df[date_col].apply(lambda x: int(x in self.jp_holidays))

        return result_df

    def make_features(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
    ) -> pd.DataFrame:
        """
        データフレーム全体に対して特徴量を作成する

        Args:
            df (pd.DataFrame): 入力データフレーム
            date_col (str): 日付カラム名

        Returns:
            pd.DataFrame: 特徴量を追加したデータフレーム
        """
        # 天気カテゴリ変換
        df = self.categorize_weather(df)

        # 数値系特徴量作成
        df = self.create_numeric_features(df)

        # カレンダー特徴量作成
        df = self.create_calendar_features(df, date_col=date_col)
        return df


if __name__ == "__main__":
    logger.info("Starting processing data...")

    args = parse_args()

    input_path = args.input_data
    base_dir = "/opt/ml/processing"

    config = load_config("/opt/ml/processing/deps/config.yaml")
    data = load_emr_output(input_path)
    feature_engineering = FeatureEngineering(config=config)
    # データの前処理
    processed_data = feature_engineering.make_features(data)
    buffer = StringIO()
    processed_data.info(buf=buffer)
    logger.info(f"Processed data info: {buffer.getvalue()}")

    # データの保存
    Path(f"{base_dir}/extract_features").mkdir(parents=True, exist_ok=True)
    processed_data.to_parquet(f"{base_dir}/extract_features/extract_features.parquet")

    logger.info("Data processing completed successfully.")
