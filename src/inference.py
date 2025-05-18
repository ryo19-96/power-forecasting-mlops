"""
エントリポイントスクリプトファイルにはmodel_fn、input_fn、predict_fn、output_fnの4つの関数が必要
https://docs.aws.amazon.com/ja_jp/sagemaker/latest/dg/neo-deployment-hosting-services-prerequisites.html
"""

import json
import logging
import os
import pickle
from typing import Any, List, Dict, Union

import numpy as np
import pandas as pd
import joblib

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def model_fn(model_dir: str) -> Any:
    """保存されたモデルを読み込む

    Args:
        model_dir (str): モデルが保存されているディレクトリパス

    Returns:
        Any: 読み込まれたモデル
    """
    model_path = os.path.join(model_dir, "model.joblib")

    return joblib.load(model_path)


def input_fn(request_body: Union[str, bytes], request_content_type: str) -> np.ndarray:
    """
    リクエストのボディをモデル入力に変換する関数

    Args:
        request_body (Union[str, bytes]): リクエストボディ
        request_content_type (str): リクエストのコンテンツタイプ

    Returns:
        np.ndarray: モデルへの入力データ

    Raises:
        ValueError: サポートされていないコンテンツタイプの場合
    """
    logger.info(f"Received request with content type: {request_content_type}")

    if request_content_type == "text/csv":
        # CSVデータをnumpy配列に変換
        df = pd.read_csv(pd.io.common.StringIO(request_body))
        return df.values
    elif request_content_type == "application/json":
        # JSONデータをnumpy配列に変換
        data = json.loads(request_body)

        if isinstance(data, dict):
            # データが辞書形式の場合（{"features": [...]}）
            if "features" in data:
                return np.array(data["features"])
            # データが辞書形式の場合（{"feature1": val1, "feature2": val2, ...}）
            return np.array(list(data.values())).reshape(1, -1)

        # データがリスト形式の場合（[[val1, val2, ...], ...]）
        return np.array(data)
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data: np.ndarray, model: Any) -> np.ndarray:
    """
    モデルを使用して予測を行う関数

    Args:
        input_data (np.ndarray): 入力データ
        model (Any): 読み込まれたモデル

    Returns:
        np.ndarray: モデルの予測結果
    """
    logger.info(f"Making prediction with input shape: {input_data.shape}")
    return model.predict(input_data)


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
    elif accept == "text/csv":
        # 予測結果をCSVに変換
        response = pd.DataFrame(prediction).to_csv(header=False, index=False)
        return response
    else:
        # デフォルトはJSON
        response = json.dumps({"predictions": prediction.tolist()})
        return response
