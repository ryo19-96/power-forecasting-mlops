import os
import zipfile
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path

import pandas as pd
import requests


class DataLoader:
    """データ読み込みを担当するクラス"""

    def __init__(self, config: Dict = None) -> None:
        """
        Args:
            config: 設定情報の辞書
                - data_dir: データディレクトリのパス
                - weather_file: 気象データファイル名
                - power_usage_dir: 電力使用量データディレクトリ名
        """
        self.config = config or {}
        self.data_dir = self.config.get('data_dir', '../../data')
        self.weather_file = self.config.get('weather_file', 'weather_data.csv')
        self.power_usage_dir = self.config.get('power_usage_dir', 'power_usage')

    def fetch_weather_api(self, city_code: str = '130010') -> Dict:
        """Web APIから気象データを取得する
        
        Args:
            city_code: 都市コード（デフォルト: 東京）
            
        Returns:
            Dict: 気象データのJSON
        """
        url = f"https://weather.tsukumijima.net/api/forecast/city/{city_code}"
        response = requests.get(url)
        return response.json()

    def load_weather_data(self, encoding: str = 'shift-jis', skiprows: List[int] = [0, 1, 2, 4, 5]) -> pd.DataFrame:
        """気象データファイルを読み込む
        
        Args:
            encoding: ファイルエンコーディング
            skiprows: スキップする行番号のリスト
            
        Returns:
            pd.DataFrame: 気象データフレーム
        """
        weather_path = os.path.join(self.data_dir, self.weather_file)
        df = pd.read_csv(weather_path, encoding=encoding, skiprows=skiprows)
        
        # 必要なカラムだけ抽出
        df = df[["年月日", "最高気温(℃)", "最低気温(℃)", "天気概況(昼：06時〜18時)"]]
        
        # カラム名を英語に変更
        df = df.rename(columns={
            "年月日": "date",
            "最高気温(℃)": "max_temp",
            "最低気温(℃)": "min_temp",
            "天気概況(昼：06時〜18時)": "weather",
        })
        
        # 日付をdatetime型に変換
        df["date"] = pd.to_datetime(df["date"], format="%Y/%m/%d")
        
        return df

    def load_power_usage_data(self) -> pd.DataFrame:
        """電力使用量データを読み込む
        
        Returns:
            pd.DataFrame: 電力使用量データフレーム
        """
        zip_dir = os.path.join(self.data_dir, self.power_usage_dir)
        result = []
        
        # ZIP内のCSVファイルからデータを読み込む
        for zip_name in sorted(os.listdir(zip_dir)):
            if not zip_name.endswith('.zip'):
                continue
            
            zip_path = os.path.join(zip_dir, zip_name)
            
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                for csv_filename in zip_ref.namelist():
                    
                    if not csv_filename.endswith('.csv'):
                        continue
                    
                    with zip_ref.open(csv_filename) as csv_file:
                        try:
                            df = pd.read_csv(csv_file, encoding="shift-jis", skiprows=54)
                            max_power = df["当日実績(５分間隔値)(万kW)"].max()
                            result.append({
                                "date": csv_filename.split('_')[0],
                                "max_power": max_power
                            })
                        except Exception as e:
                            print(f"Error reading {csv_filename}: {e}")
        
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
        integrated_df = pd.merge(weather_df, power_usage_df, on="date", how="inner")
        
        return integrated_df