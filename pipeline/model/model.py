import logging
import os

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from omegaconf import DictConfig
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class PowerForecastModel:
    """電力需要予測モデルクラス"""

    def __init__(self, config: DictConfig | None = None) -> None:
        """
        Args:
            config: 設定情報
        """
        self.config = config or {}
        self.model = None
        self.target_col = self.config.get("target", "max_power")
        self.model_params = self.config.get("model_params", {})
        self.exclude_cols = [self.target_col, "date"]
        self.test_size = self.config.get("test_size", 0.2)
        self.random_state = self.config.get("random_state", 10)

    def train_test_split(self, df: pd.DataFrame, test_date: str = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """時系列データを訓練データとテストデータに分割する

        Args:
            df: 入力データフレーム
            test_date: テストデータの開始日付（例: '2024-10-01'）
                       指定がない場合は、self.test_sizeに基づいて分割

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: 訓練データとテストデータ
        """
        # 日付でソート
        df_sorted = df.sort_values("date")

        if test_date:
            # 指定した日付で分割
            df_train = df_sorted[df_sorted["date"] < test_date]
            df_test = df_sorted[df_sorted["date"] >= test_date]
        else:
            # データ数に基づいて分割
            train_size = int(len(df_sorted) * (1 - self.test_size))
            df_train = df_sorted.iloc[:train_size]
            df_test = df_sorted.iloc[train_size:]

        return df_train, df_test

    def prepare_data(
        self, df_train: pd.DataFrame, df_test: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        """モデル訓練用にデータを準備する

        Args:
            df_train: 訓練データ
            df_test: テストデータ

        Returns:
            Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]: X_train, y_train, X_test, y_test
        """
        X_train = df_train.drop(columns=self.exclude_cols)
        y_train = df_train[self.target_col]

        X_test = df_test.drop(columns=self.exclude_cols)
        y_test = df_test[self.target_col]

        return X_train, y_train, X_test, y_test

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """モデルを訓練する

        Args:
            X_train: 訓練データの特徴量
            y_train: 訓練データの目的変数
        """
        # デフォルトパラメータ
        default_params = {"objective": "regression", "metric": "rmse", "boosting_type": "gbdt", "verbosity": -1}

        # デフォルトパラメータをconfigで上書き
        params = {**default_params, **self.model_params}

        # モデルのインスタンス化と訓練
        self.model = lgb.LGBMRegressor(**params)
        self.model.fit(X_train, y_train)

        # 特徴量重要度を記録
        self.feature_names = X_train.columns.tolist()
        self.feature_importances = self.model.feature_importances_

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """予測を行う

        Args:
            X: 予測したいデータの特徴量

        Returns:
            np.ndarray: 予測値
        """
        if self.model is None:
            raise ValueError("モデルが未訓練です。")

        return self.model.predict(X)

    def evaluate(self, y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
        """モデルを評価する

        Args:
            y_true: 実際の値
            y_pred: 予測値

        Returns:
            Dict[str, float]: 評価メトリクスの辞書
        """
        metrics = {
            "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
            "mse": mean_squared_error(y_true, y_pred),
            "mae": mean_absolute_error(y_true, y_pred),
            "r2": r2_score(y_true, y_pred),
        }

        return metrics

    def save_model(self, filepath: str) -> None:
        """モデルを保存する

        Args:
            filepath: 保存先のパス
        """
        if self.model is None:
            raise ValueError("モデルが訓練されていません。先にtrain()を呼び出してください。")

        # ディレクトリがなければ作成
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # モデルを保存
        joblib.dump(self.model, filepath)

    def load_model(self, filepath: str) -> None:
        """モデルを読み込む

        Args:
            filepath: モデルファイルのパス
        """
        self.model = joblib.load(filepath)

    def get_feature_importance(self) -> pd.DataFrame:
        """特徴量重要度を取得する

        Returns:
            pd.DataFrame: 特徴量名と重要度を含むデータフレーム
        """
        if self.model is None:
            raise ValueError("モデルが訓練されていません。")

        df_importance = pd.DataFrame({"feature": self.feature_names, "importance": self.feature_importances})

        return df_importance.sort_values("importance", ascending=False)
