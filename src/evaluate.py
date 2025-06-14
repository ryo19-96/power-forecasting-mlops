import subprocess
import sys
import tarfile

# 必要なパッケージをその場でインストール
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "lightgbm", "scikit-learn"], check=True)

import argparse
import json
import logging
import os
from pathlib import Path
from typing import List, Tuple, Union

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.sparse import spmatrix
from sklearn.metrics import mean_squared_error

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def parse_args() -> argparse.Namespace:
    """
    SageMakerから渡される評価引数をパースする

    Returns:
        argparse.Namespace: パースされた引数
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model-path", type=str, default=os.environ.get("SM_MODEL_PATH", "/opt/ml/processing/model/model.tar.gz"),
    )
    parser.add_argument(
        "--test-path", type=str, default=os.environ.get("SM_CHANNEL_TEST", "/opt/ml/processing/test/test.csv"),
    )
    parser.add_argument(
        "--feature-names-path",
        type=str,
        default=os.environ.get("SM_FEATURE_NAMES", "/opt/ml/processing/train/features.txt"),
    )
    parser.add_argument(
        "--output-path", type=str, default=os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/processing/evaluation"),
    )

    return parser.parse_args()


def load_model(model_tar_path: str) -> lgb.Booster:
    """model.tar.gz から model.pickle を取り出してモデルを返す
    Args:
        model_tar_path (str): モデルのtar.gzファイルのパス
    Returns:
        lgb.Booster: 学習済みモデル
    """
    extract_dir = "/tmp/model"  # noqa: S108
    Path(extract_dir).mkdir(exist_ok=True)
    with tarfile.open(model_tar_path, "r:gz") as tar:
        tar.extractall(path=extract_dir)

    model_path = next(Path(extract_dir).rglob("model.joblib"))

    return joblib.load(model_path)


def get_feature_names(feature_name_path: str) -> List[str]:
    """モデルの特徴量名を取得する

    Returns:
        List[str]: 特徴量名のリスト
    """
    with Path(feature_name_path).open() as f:
        feature_names = [line.strip() for line in f if line.strip()]
    return feature_names


def evaluate_model(y_true: pd.Series, y_pred: Union[np.ndarray, pd.Series, spmatrix], output_path: str) -> None:
    """モデルの評価を行い、結果をJSONファイルに保存する

    Args:
        y_true (pd.Series): 実際の値
        y_pred (pd.Series): 予測値
        output_path (str): 評価結果を保存するパス
    """
    # sagemakerのJsonGetで取得しやすいような形式にする
    metrics = {"regression_metrics": {"mse": {"value": mean_squared_error(y_true, y_pred)}}}
    Path(output_path).mkdir(parents=True, exist_ok=True)

    with (Path(output_path) / "evaluation.json").open("w") as f:
        json.dump(metrics, f)


def load_test_data(
    test_data_path: str,
    feature_names: List[str],
    target_col: str = "max_power",
) -> Tuple[pd.DataFrame, pd.Series]:
    """テストデータを読み込んで必要なデータを返す

    Args:
        test_data_path (str): テストデータのパス
        feature_names (List[str]): 特徴量名のリスト
        target_col (str): 目的変数のカラム名

    Returns:
        pd.DataFrame: 特徴量データ
        pd.Series: 目的変数データ
    """
    test_data = pd.read_csv(test_data_path, header=None, names=feature_names)
    X_test = test_data.drop(columns=[target_col])
    y_true = test_data[target_col]
    return X_test, y_true


if __name__ == "__main__":
    logger.info("Starting evaluate...")

    args = parse_args()
    # コマンドライン引数の取得
    model_path = args.model_path
    test_data_path = args.test_path
    feature_names_path = args.feature_names_path
    output_path = args.output_path

    # モデルのロード
    model = load_model(model_path)

    # 特徴量名の取得
    feature_names = get_feature_names(feature_names_path)

    # テストデータのロード
    X_test, y_true = load_test_data(test_data_path, feature_names)

    # 予測と評価
    y_pred = model.predict(X_test)
    evaluate_model(y_true, y_pred, output_path)
    logger.info("finished evaluate...")
