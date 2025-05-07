import datetime
from typing import Dict, List, Optional, Union

import holidays
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from common.feature_encoder import FeatureEncoder


class FeatureEngineering:
    """特徴量エンジニアリングを行うクラス"""

    def __init__(self, config: Optional[DictConfig] = None) -> None:
        """
        Args:
            config: 設定情報（省略可能）
        """
        self.config = config
        self.encoders_dict = {}
        self.jp_holidays = holidays.Japan()

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
        result_df["hot"] = (df["max_temp"] >= 30).astype(int)
        
        # 冬日フラグ（最低気温が5℃以下か）
        result_df["cold"] = (df["min_temp"] <= 5).astype(int)
        
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
        result_df["holiday"] = result_df[date_col].apply(
            lambda x: int(x in self.jp_holidays)
        )
        
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

    def make_features(self, df: pd.DataFrame) -> pd.DataFrame:
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
        df = self.create_calendar_features(df)
        
        # configでエンコーダーの指定があればエンコーダーを適用
        if self.config and "encoders" in self.config:
            df = self.encode_features(df, self.config)
        
        return df