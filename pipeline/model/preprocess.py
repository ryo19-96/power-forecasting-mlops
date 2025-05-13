import subprocess
import sys
import os

# 必要なパッケージをその場でインストール
subprocess.run(
    [sys.executable, "-m", "pip", "install", "--quiet", "holidays", "omegaconf", "category-encoders"], check=True
)
sys.path.append("/opt/ml/processing/deps")
import logging

import holidays
import numpy as np
import pandas as pd
from typing import Union, Tuple
from pathlib import Path
from omegaconf import DictConfig, OmegaConf

from feature_encoder import FeatureEncoder
import argparse
import pathlib
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

HOT_DAY_THRESHOLD = 30
COLD_DAY_THRESHOLD = 5


def load_config(config_path: str) -> DictConfig:
    """設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス

    Returns:
        DictConfig: 設定情報
    """
    config = DictConfig(OmegaConf.load(config_path))
    return config


def load_data(file_path: str) -> pd.DataFrame:
    """データを読み込む

    Args:
        file_path: データファイルのパス

    Returns:
        pd.DataFrame: 読み込んだデータフレーム
    """
    df = pd.read_pickle(file_path)
    return df


class FeatureEngineering:
    """特徴量エンジニアリングを行うクラス"""

    def __init__(self, config: Union[DictConfig, None] = None) -> None:
        """
        Args:
            config: 設定情報（省略可能）
        """
        self.config = config
        self.encoders_dict = {}
        self.jp_holidays = holidays.Japan()  # type: ignore[attr-defined]

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
        elif any(keyword in weather for keyword in ["雪", "ゆき"]):
            return "雪"

        # 雷系
        if "雷" in weather:
            if any(keyword in weather for keyword in ["雨", "あめ"]):
                return "雷雨"
            elif any(keyword in weather for keyword in ["晴", "日射"]):
                return "晴れ(雷あり)"
            elif any(keyword in weather for keyword in ["曇", "くもり"]):
                return "曇り(雷あり)"
            else:
                return "雷"

        # 晴れ系
        if "快晴" in weather:
            return "快晴"
        elif any(keyword in weather for keyword in ["晴", "日射"]):
            if any(keyword in weather for keyword in ["曇", "くもり"]):
                return "晴れ時々曇り"
            elif any(keyword in weather for keyword in ["雨", "あめ", "雷"]):
                return "晴れ時々雨"
            else:
                return "晴れ"

        # 曇り系
        elif any(keyword in weather for keyword in ["曇", "くもり"]):
            if any(keyword in weather for keyword in ["雨", "あめ"]):
                return "曇り時々雨"
            else:
                return "曇り"

        # 雨系
        elif any(keyword in weather for keyword in ["雨", "あめ"]):
            return "雨"

        # その他
        else:
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

        # 冷房度日：平均気温が18℃を超えた分だけ冷房が必要と考える指標
        result_df["cdd"] = (result_df["avg"] - 18).clip(lower=0)

        # 暖房度日：平均気温が18℃未満の場合、暖房が必要と考える指標
        result_df["hdd"] = (18 - result_df["avg"]).clip(lower=0)

        # 猛暑日フラグ（最高気温が30℃以上か）
        result_df["hot"] = (df["max_temp"] >= HOT_DAY_THRESHOLD).astype(int)

        # 冬日フラグ（最低気温が5℃以下か）
        result_df["cold"] = (df["min_temp"] <= COLD_DAY_THRESHOLD).astype(int)

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

    def encode_features(self, df: pd.DataFrame, config: DictConfig, reset_encoders: bool = False) -> pd.DataFrame:
        """特徴量をエンコードする

        Args:
            df: 特徴量を含むデータフレーム
            config: 設定ファイルの内容
            reset_encoders: エンコーダーを初期化するかどうか

        Returns:
            pd.DataFrame: エンコードされたデータフレーム
        """
        if reset_encoders:
            self.encoders_dict = {}

        result_df = df.copy()

        if "encoders" in config:
            for params in config["encoders"]:
                if params["name"] not in self.encoders_dict:
                    encoder = FeatureEncoder(**params)
                    result_df = encoder.fit_transform(result_df)
                    self.encoders_dict[params["name"]] = encoder
                else:
                    encoder = self.encoders_dict[params["name"]]
                    result_df = encoder.transform(result_df)

        return result_df

    def make_features(self, df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
        """データフレーム全体に対して特徴量を作成する

        Args:
            df: 入力データフレーム

        Returns:
            pd.DataFrame: 特徴量を追加したデータフレーム
        """
        # 天気カテゴリ変換
        df = self.categorize_weather(df)

        # 数値系特徴量作成
        df = self.create_numeric_features(df)

        # カレンダー特徴量作成
        df = self.create_calendar_features(df, date_col=date_col)

        # configでエンコーダーの指定があればエンコーダーを適用
        if self.config and "encoders" in self.config:
            df = self.encode_features(df, self.config)

        return df


def format_target_first(df: pd.DataFrame, target_col: str = "max_power") -> pd.DataFrame:
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


def train_test_split(
    df: pd.DataFrame,
    test_date: Union[str, None] = None,
    test_size: float = 0.2,
    date_col: str = "date",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    時系列データを訓練データとテストデータに分割する

    Args:
        df: 入力データフレーム
        test_date: テストデータの開始日付（例: '2024-10-01'）
                    指定がない場合は、test_sizeに基づいて分割
        test_size: テストデータの割合（test_dateが指定されていない場合に使用）

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 訓練データとテストデータ
    """
    df = format_target_first(df)
    # 日付でソート
    df_sorted = df.sort_values(date_col)

    if test_date:
        # 指定した日付で分割
        df_train = df_sorted[df_sorted[date_col] < test_date]
        df_test = df_sorted[df_sorted[date_col] >= test_date]
    else:
        # データ数に基づいて分割
        train_size = int(len(df_sorted) * (1 - test_size))
        df_train = df_sorted.iloc[:train_size]
        df_test = df_sorted.iloc[train_size:]

    df_train = df_train.drop(columns=[date_col]).reset_index(drop=True)
    df_test = df_test.drop(columns=[date_col]).reset_index(drop=True)

    return df_train, df_test


def save_column_names(df: pd.DataFrame, output_path: str = "/opt/ml/processing/train/features.txt") -> None:
    """特徴量重要度のプロットのためカラム名を保存する

    Args:
        df: 入力データフレーム
        output_path: 出力パス
    """
    feature_names = df.columns.tolist()

    with open(output_path, "w") as f:
        for name in feature_names:
            f.write(f"{name}\n")


if __name__ == "__main__":
    logger.info("Starting processing data...")
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", type=str)
    args = parser.parse_args()
    input_path = args.input_data
    base_dir = "/opt/ml/processing"

    config = load_config("/opt/ml/processing/deps/config.yaml")
    data = load_data(input_path)
    feature_engineering = FeatureEngineering(config=config)
    # データの前処理
    processed_data = feature_engineering.make_features(data)
    train_data, test_data = train_test_split(processed_data, test_date="2024-10-01")
    # カラム名を保存
    save_column_names(train_data, output_path=f"{base_dir}/train/features.txt")

    # データの保存
    Path(f"{base_dir}/train").mkdir(parents=True, exist_ok=True)
    train_data.to_csv(f"{base_dir}/train/train.csv", index=False, header=False)
    Path(f"{base_dir}/test").mkdir(parents=True, exist_ok=True)
    test_data.to_csv(f"{base_dir}/test/test.csv", index=False, header=False)
    logger.info("Finished processing data...")
