"""
エントリポイントスクリプトファイルにはmodel_fn、input_fn、predict_fn、output_fnの4つの関数が必要
https://docs.aws.amazon.com/ja_jp/sagemaker/latest/dg/neo-deployment-hosting-services-prerequisites.html
"""

import json
import logging
import os
import pickle
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Tuple, Union

import joblib
import numpy as np
import pandas as pd

from preprocess import FeatureEngineering, load_config

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def model_fn(model_dir: str) -> Dict[str, Any]:
    """保存されたモデル・設定ファイル・エンコーダーを読み込む

    Args:
        model_dir (str): モデルが保存されているディレクトリパス

    Returns:
        Dict[str, Any]: モデルとエンコーダーを含む辞書
    """
    # モデルの読み込み
    model_path = os.path.join(model_dir, "model.joblib")
    model = joblib.load(model_path)

    # config.yaml の読み込み
    config_path = os.path.join(model_dir, "code", "config.yaml")
    config = load_config(config_path)

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

    return {"model": model, "config": config, "encoders": encoders_dict, "feature_names": feature_names}


def apply_encoders(df: pd.DataFrame, encoders_dict: Dict[str, Any]) -> pd.DataFrame:
    """
    エンコーダーを適用する

    Args:
        df (pd.DataFrame): 入力データ
        encoders_dict (Dict[str, Any]): エンコーダーの辞書

    Returns:
        pd.DataFrame: エンコードされたデータ
    """
    result_df = df.copy()
    for encoder in encoders_dict.values():
        # エンコーダーの対象の列が存在するか確認
        if hasattr(encoder, "columns"):
            columns_exist = all(col in result_df.columns for col in encoder.columns)
            if columns_exist:
                result_df = encoder.transform(result_df)
    return result_df


def astype_df(df: pd.DataFrame) -> pd.DataFrame:
    """データフレームのカラムの型を変換する

    Args:
        df (pd.DataFrame): 入力データ

    Returns:
        pd.DataFrame: 型変換されたデータフレーム
    """
    for col in df.columns:
        # 日付変換
        if col == "date":
            df[col] = pd.to_datetime(df[col], errors="coerce")
        # 数値変換（strでもOK）
        elif col in {"max_temp", "min_temp"}:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # 明示的にstrへ変換
        elif col == "weather":
            df[col] = df[col].astype(str)
    return df


def input_fn(request_body: Union[str, bytes], request_content_type: str) -> pd.DataFrame:
    """
    リクエストボディを DataFrame に変換して返す
    """
    logger.info(f"Received request with content type: {request_content_type}")

    COLUMNS = ["date", "max_temp", "min_temp", "weather"]

    # text/csv なら CSV 文字列→DataFrame
    if request_content_type.startswith("text/csv"):
        df = pd.read_csv(StringIO(request_body), header=None, names=COLUMNS)
        return astype_df(df)

    # application/json 系
    if request_content_type.startswith("application/json"):
        payload = json.loads(request_body)

        # [{...}, {...}] 形式
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return astype_df(pd.DataFrame(payload)[COLUMNS])

        # {"feature": val, ...} 単一レコード形式
        if isinstance(payload, dict) and "features" not in payload:
            return astype_df(pd.DataFrame([payload])[COLUMNS])

        # {"features": [[...]]} 形式
        if isinstance(payload, dict) and "features" in payload:
            return astype_df(pd.DataFrame(payload["features"], columns=COLUMNS))
    msg = f"Unsupported content type: {request_content_type}"
    raise ValueError(msg)


def predict_fn(input_data: pd.DataFrame, model_dict: Dict[str, Any]) -> np.ndarray:
    """
    モデルを使用して予測を行う関数（前処理を含む）

    Args:
        input_data (pd.DataFrame): 入力データ
        model_dict (Dict[str, Any]): モデルとエンコーダーを含む辞書

    Returns:
        np.ndarray: モデルの予測結果
    """
    model = model_dict["model"]
    config = model_dict["config"]
    encoders_dict = model_dict.get("encoders", {})
    feature_names = model_dict.get("feature_names", [])

    # 特徴量エンジニアリング
    feature_engineering = FeatureEngineering(config=config)
    input_data = feature_engineering.make_features(df=input_data, date_col="date")

    # エンコーダー適用（存在する場合のみ）
    if encoders_dict:
        input_data = apply_encoders(input_data, encoders_dict)

    # 学習時のカラム順序に合わせる
    if feature_names:
        # 特徴量名と入力データの列名の交差部分を取得
        common_columns = [col for col in feature_names if col in input_data.columns]
        if common_columns:
            input_data = input_data[common_columns]

    return model.predict(input_data.values)


def output_fn(prediction: np.ndarray, accept: str) -> Tuple[Union[str, bytes], str]:
    """
    推論結果を (body, content_type) で返す
    SageMaker で正しく Content-Type を伝えるために必須
    """
    # 期待されるレスポンス形式が JSON 系か、あるいは空なら JSON で返す
    if not accept or accept.startswith("application/json"):
        body = json.dumps({"predictions": prediction.tolist()})
        content_type = "application/json"
        return body, content_type

    # CSV を要求された場合
    if accept.startswith("text/csv"):
        body = pd.DataFrame(prediction).to_csv(header=False, index=False)
        content_type = "text/csv"
        return body, content_type

    # それ以外はすべて JSON で対応
    body = json.dumps({"predictions": prediction.tolist()})
    content_type = "application/json"
    return body, content_type
