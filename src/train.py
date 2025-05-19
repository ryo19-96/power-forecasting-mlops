import argparse
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def parse_args() -> argparse.Namespace:
    """
    SageMakerから渡される学習引数をパースする

    Returns:
        argparse.Namespace: パースされた引数
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR"))
    parser.add_argument("--train", type=str, default="/opt/ml/input/data/train")

    # パラメータ
    parser.add_argument("--n_estimators", type=int, default=100)
    parser.add_argument("--learning_rate", type=float, default=0.1)
    parser.add_argument("--random_state", type=int, default=10)

    return parser.parse_args()


def load_data(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    CSVファイルから学習データを読み込む

    Args:
        file_path (str): データファイルのパス

    Returns:
        Tuple[np.ndarray, np.ndarray]: 特徴量と目標値のタプル
    """
    logger.info(f"Loading data from {file_path}")

    # ヘッダーなしCSVを読み込む（preprocess.pyの出力形式に合わせる）
    data = pd.read_csv(os.path.join(file_path, "train.csv"), header=None)

    # 最初の列が目的変数
    y = data.iloc[:, 0].values
    X = data.iloc[:, 1:].values

    logger.info(f"Data shape: X={X.shape}, y={y.shape}")
    return X, y


def train(X: np.ndarray, y: np.ndarray, hyperparameters: Dict[str, Any]) -> LGBMRegressor:
    """LightGBMモデルをトレーニングする

    Args:
        X (np.ndarray): 特徴量
        y (np.ndarray): 目標値
        hyperparameters (Dict[str, Any]): モデルのハイパーパラメータ

    Returns:
        LGBMRegressor: トレーニング後のモデル
    """
    logger.info("Starting model training")

    # ハイパーパラメータを設定してモデルを作成
    model = LGBMRegressor(
        n_estimators=hyperparameters.get("n_estimators", 100),
        learning_rate=hyperparameters.get("learning_rate", 0.1),
        random_state=hyperparameters.get("random_state", 10),
        objective="regression",
        metric="rmse",
    )

    # モデルのトレーニング
    model.fit(X, y)

    return model


def save_model(model: LGBMRegressor, model_dir: str, train_dir: str) -> None:
    """
    モデルを保存する

    Args:
        model (LGBMRegressor): 保存するモデル
        model_dir (str): モデルの保存先ディレクトリ
        train_dir (str): train.csvが入っているディレクトリ
    """

    # モデルを保存
    model_path = os.path.join(model_dir, "model.joblib")
    joblib.dump(model, model_path)

    # train.csvが保存されているディレクトリにあるencoders.pklとreatures.txtをコピー
    encoders_path = os.path.join(train_dir, "encoders.pkl")
    features_path = os.path.join(train_dir, "features.txt")
    if Path(encoders_path).exists():
        shutil.copy(encoders_path, os.path.join(model_dir, "encoders.pkl"))
    if Path(features_path).exists():
        shutil.copy(features_path, os.path.join(model_dir, "features.txt"))

    logger.info("Model and related files saved successfully")


if __name__ == "__main__":
    args = parse_args()

    # ハイパーパラメータの設定
    hyperparameters = {
        "n_estimators": args.n_estimators,
        "learning_rate": args.learning_rate,
        "random_state": args.random_state,
    }

    # データの読み込み
    X_train, y_train = load_data(args.train)

    # モデルの学習
    model = train(X_train, y_train, hyperparameters)

    # モデルの保存
    save_model(model, args.model_dir, args.train)
