"""
エントリポイントスクリプトファイルにはmodel_fn、input_fn、predict_fn、output_fnの4つの関数が必要
https://docs.aws.amazon.com/ja_jp/sagemaker/latest/dg/neo-deployment-hosting-services-prerequisites.html
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Dict, Union

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def model_fn(model_dir: str) -> Dict[str, Any]:
    """保存されたモデルとエンコーダーを読み込む

    Args:
        model_dir (str): モデルが保存されているディレクトリパス

    Returns:
        Dict[str, Any]: モデルとエンコーダーを含む辞書
    """
    # モデルの読み込み
    model_path = os.path.join(model_dir, "model.joblib")
    model = joblib.load(model_path)

    # エンコーダーの読み込み（存在する場合）
    encoders_dict = {}
    encoders_path = os.path.join(model_dir, "encoders.pkl")
    if Path(encoders_path).exists():
        with Path(encoders_path).open("rb") as f:
            encoders_dict = pickle.load(f)

    # 特徴量名の読み込み（存在する場合）
    feature_names = []
    feature_names_path = os.path.join(model_dir, "features.txt")
    if Path(feature_names_path).exists():
        with Path(feature_names_path).open("r") as f:
            feature_names = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(feature_names)} feature names")

    return {"model": model, "encoders": encoders_dict, "feature_names": feature_names}


def apply_encoders(df: pd.DataFrame, encoders_dict: Dict[str, Any]) -> pd.DataFrame:
    """エンコーダーを適用する

    Args:
        df (pd.DataFrame): 入力データ
        encoders (Dict[str, Any]): エンコーダーの辞書

    Returns:
        pd.DataFrame: エンコードされたデータ
    """
    result_df = df.copy()

    for encoder in encoders_dict.values():
        # エンコーダーの対象の列が存在するか確認
        columns_exist = all(col in df.columns for col in encoder.columns)
        if columns_exist:
            result_df = encoder.transform(result_df)

    return result_df


def input_fn(request_body: Union[str, bytes], request_content_type: str) -> pd.DataFrame:
    """
    リクエストのボディをモデル入力に変換する関数

    Args:
        request_body (Union[str, bytes]): リクエストボディ
        request_content_type (str): リクエストのコンテンツタイプ

    Returns:
        pd.DataFrame: モデルへの入力データ（データフレーム形式）

    Raises:
        ValueError: サポートされていないコンテンツタイプの場合
    """
    logger.info(f"Received request with content type: {request_content_type}")

    if request_content_type == "text/csv":
        # CSVデータをデータフレームに変換
        df = pd.read_csv(pd.io.common.StringIO(request_body))
        return df
    if request_content_type == "application/json":
        # JSONデータをデータフレームに変換
        data = json.loads(request_body)

        if isinstance(data, dict):
            # データが辞書形式の場合（{"features": [...]}）
            if "features" in data:
                return pd.DataFrame(data["features"])
            # データが辞書形式の場合（{"feature1": val1, "feature2": val2, ...}）
            return pd.DataFrame([data])

        # データがリスト形式の場合（[[val1, val2, ...], ...]）
        return pd.DataFrame(data)

    msg = f"Unsupported content type: {request_content_type}"
    raise ValueError(msg)


def predict_fn(input_data: pd.DataFrame, model_dict: Dict[str, Any]) -> np.ndarray:
    """
    モデルを使用して予測を行う関数

    Args:
        input_data (pd.DataFrame): 入力データ
        model_dict (Dict[str, Any]): モデルとエンコーダーを含む辞書

    Returns:
        np.ndarray: モデルの予測結果
    """
    model = model_dict["model"]
    encoders = model_dict.get("encoders", {})
    feature_names = model_dict.get("feature_names", [])

    logger.info(f"Input data shape before preprocessing: {input_data.shape}")

    # 特徴量名がある場合、その順序に合わせる
    if feature_names and len(feature_names) > 0:
        # 特徴量名と入力データの列名の交差部分を取得
        common_columns = [col for col in feature_names if col in input_data.columns]
        if common_columns:
            input_data = input_data[common_columns]
            logger.info(f"Aligned data to match feature names: {common_columns}")

    # エンコーダーを適用
    if encoders:
        input_data = apply_encoders(input_data, encoders)

    logger.info(f"Making prediction with input shape: {input_data.shape}")
    return model.predict(input_data.values)


def output_fn(prediction: np.ndarray, accept: str) -> Union[str, bytes]:
    """
    モデルの予測結果をレスポンスに変換する関数

    Args:
        prediction (np.ndarray): モデルの予測結果
        accept (str): クライアントが受け入れるレスポンス形式

    Returns:
        Union[str, bytes]: フォーマットされた予測結果

    Raises:
        ValueError: サポートされていないレスポンス形式の場合
    """
    logger.info(f"Formatting output with accept type: {accept}")

    if accept == "application/json":
        # 予測結果をJSONに変換
        response = json.dumps({"predictions": prediction.tolist()})
        return response
    if accept == "text/csv":
        # 予測結果をCSVに変換
        response = pd.DataFrame(prediction).to_csv(header=False, index=False)
        return response
    # デフォルトはJSON
    response = json.dumps({"predictions": prediction.tolist()})
    return response
