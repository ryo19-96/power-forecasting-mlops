import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Union

import pandas as pd
from omegaconf import OmegaConf, DictConfig

from data_loader import DataLoader
from pipeline.model.preprocess import FeatureEngineering
from model import PowerForecastModel
from visualization import Visualizer


# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class PowerForecastPipeline:
    """電力需要予測パイプラインクラス"""

    def __init__(self, config_path: str = "config.yaml", output_dir: str = None) -> None:
        """
        Args:
            config_path: 設定ファイルのパス
            output_dir: 出力ディレクトリ（指定がない場合は現在時刻のタイムスタンプを使用）
        """
        logger.info(f"設定ファイル '{config_path}' を読み込み中...")
        self.config = OmegaConf.load(config_path)

        # 出力ディレクトリの設定
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = os.path.join("output", timestamp)
        else:
            self.output_dir = output_dir

        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"出力ディレクトリ: {self.output_dir}")

        # 各コンポーネントの初期化
        self.data_loader = DataLoader(self.config.get("data", {}))
        self.feature_engineering = FeatureEngineering(self.config)
        self.model = PowerForecastModel(self.config.get("model", {}))
        self.visualizer = Visualizer(self.output_dir)

    def run(self, test_date: Optional[str] = None) -> Dict[str, float]:
        """パイプラインを実行する

        Args:
            test_date: テストデータの開始日付（Noneの場合はconfigの値を使用）

        Returns:
            Dict[str, float]: モデルの評価メトリクス
        """
        try:
            # データ読み込み
            logger.info("データを読み込み中...")
            data = self.data_loader.merge_data()

            # 特徴量エンジニアリング
            logger.info("特徴量エンジニアリングを実行中...")
            data = self.feature_engineering.make_features(data)

            # データ分割
            test_date = test_date or self.config.get("model", {}).get("test_date", None)
            logger.info(f"データを分割中... (テスト日付: {test_date or '設定なし'})")
            df_train, df_test = self.model.train_test_split(data, test_date)

            # データ準備
            X_train, y_train, X_test, y_test = self.model.prepare_data(df_train, df_test)

            # モデル訓練
            logger.info("モデルを訓練中...")
            self.model.train(X_train, y_train)

            # モデル予測
            logger.info("テストデータで予測を実行中...")
            y_pred = self.model.predict(X_test)

            # モデル評価
            logger.info("モデルを評価中...")
            metrics = self.model.evaluate(y_test, y_pred)
            for metric_name, value in metrics.items():
                logger.info(f"{metric_name}: {value:.4f}")

            # 可視化
            logger.info("結果を可視化中...")

            # 特徴量重要度の可視化
            feature_importance = self.model.get_feature_importance()
            self.visualizer.plot_feature_importance(
                feature_importance, plot_features=min(20, len(feature_importance)), save_name="feature_importance"
            )

            # 予測と実際の値の比較
            self.visualizer.plot_prediction_vs_actual(
                y_test, y_pred, dates=df_test["date"], save_name="prediction_vs_actual"
            )

            # 評価メトリクスの可視化
            self.visualizer.plot_evaluation_metrics(metrics, save_name="model_metrics")

            # 特徴量の分布の可視化
            self.visualizer.plot_feature_distributions(
                X_train,
                columns=self.config.get("features", {}).get("numerical", None),
                save_name="feature_distributions",
            )

            # 相関ヒートマップの作成
            self.visualizer.correlation_heatmap(df_train, save_name="correlation_heatmap")

            # モデルの保存
            model_path = os.path.join(self.output_dir, "model.joblib")
            self.model.save_model(model_path)
            logger.info(f"モデルを保存しました: {model_path}")

            return metrics

        except Exception as e:
            logger.error(f"パイプライン実行中にエラーが発生しました: {str(e)}")
            raise


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="電力需要予測パイプラインを実行")
    parser.add_argument("--config", type=str, default="config.yaml", help="設定ファイルのパス")
    parser.add_argument("--output", type=str, default=None, help="出力ディレクトリ（省略可）")
    parser.add_argument("--test_date", type=str, default=None, help="テストデータの開始日付（例: 2024-10-01）")

    args = parser.parse_args()

    # パイプラインの実行
    pipeline = PowerForecastPipeline(args.config, args.output)
    pipeline.run(args.test_date)


if __name__ == "__main__":
    main()
