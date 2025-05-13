import subprocess
import sys

# 必要なパッケージをその場でインストール（1回目だけ多少遅い）
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        "seaborn",
        "lightgbm",
        "matplotlib",
        "japanize-matplotlib",
        "scikit-learn",
    ],
    check=True,
)
import argparse
import logging
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import japanize_matplotlib  # noqa: F401
import joblib
import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.sparse import spmatrix
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class Visualizer:
    """モデルの評価や特徴量の可視化を行うクラス"""

    def __init__(self, output_dir: str, model: Any, feature_names_path: str) -> None:
        """
        Args:
            output_dir: 出力ディレクトリ
        """
        self.output_dir = output_dir
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.model = model
        self.feature_names_path = feature_names_path
        self.feature_names = self.get_feature_names(feature_names_path)

    def load_test_data(
        self,
        test_data_path: str,
        target_col: str = "max_power",
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """テストデータを読み込んで必要なデータを返す

        Args:
            test_data_path (str): テストデータのパス
            target_col (str): 目的変数のカラム名

        Returns:
            Tuple[pd.DataFrame, pd.Series]: 特徴量データと目的変数データ
        """
        test_data = pd.read_csv(test_data_path, names=self.feature_names, header=None)
        X_test = test_data.drop(columns=[target_col])
        y_true = test_data[target_col]
        return X_test, y_true

    def evaluate(self, y_true: pd.Series, y_pred: Union[np.ndarray, pd.Series, spmatrix]) -> Dict[str, float]:
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

    def get_feature_names(self, feature_name_path: str) -> List[str]:
        """モデルの特徴量名を取得する

        Returns:
            List[str]: 特徴量名のリスト
        """
        with Path(feature_name_path).open() as f:
            feature_names = [line.strip() for line in f if line.strip()]
        return feature_names

    def get_feature_importance(self) -> pd.DataFrame:
        """特徴量重要度を取得する
        使用するlightgbmのインターフェースによって異なるため、条件分岐で取得する

        Returns:
            pd.DataFrame: 特徴量と重要度を含むデータフレーム
        """
        if hasattr(self.model, "feature_name_") and hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
        elif hasattr(self.model, "feature_name") and hasattr(self.model, "feature_importance"):
            importances = self.model.feature_importance()
        else:
            msg = "モデルの特徴量取得に失敗しました"
            raise ValueError(msg)
        # 特徴量名の先頭は目的変数のため除外して渡す
        df_importance = pd.DataFrame({"feature": self.feature_names[1:], "importance": importances})
        return df_importance.sort_values("importance", ascending=False)

    def plot_feature_importance(
        self,
        feature_importance_df: pd.DataFrame,
        plot_features: int = 20,
        save_name: str = "feature_importance",
        figsize: Union[Tuple[int, int], None] = None,
    ) -> None:
        """特徴量重要度のプロットを行う

        Args:
            feature_importance_df: 特徴量と重要度を含むデータフレーム（columns=['feature', 'importance']）
            plot_features: 表示する特徴量の数
            save_name: 保存するファイル名
            figsize: グラフのサイズ（指定がない場合は自動的に計算）
        """
        # 重要度でソート
        df_importance = feature_importance_df.sort_values("importance", ascending=False)

        # 表示する特徴量を指定数に制限
        df_plot = df_importance.iloc[:plot_features]

        # グラフサイズを計算（指定がない場合）
        if figsize is None:
            figsize = (10, max(5, plot_features / 2))

        plt.figure(figsize=figsize)
        sns.barplot(x="importance", y="feature", data=df_plot, palette="viridis")
        plt.title("特徴量重要度")
        plt.tight_layout()

        # ファイルに保存
        plt.savefig(f"{self.output_dir}/{save_name}.png", format="png", dpi=300)

        # CSVファイルにも保存
        df_importance.to_csv(f"{self.output_dir}/{save_name}.csv", index=False)

        plt.close()

    def plot_prediction_vs_actual(
        self,
        y_true: Union[pd.Series, np.ndarray],
        y_pred: np.ndarray,
        dates: Union[pd.Series, None] = None,
        save_name: str = "prediction_vs_actual",
        figsize: Tuple[int, int] = (15, 8),
    ) -> None:
        """予測値と実際の値の比較プロットを行う

        Args:
            y_true: 実際の値
            y_pred: 予測値
            dates: 日付（指定がある場合は時系列プロットも作成）
            save_name: 保存するファイル名
            figsize: グラフサイズ
        """
        # スキャッタープロット
        plt.figure(figsize=figsize)

        plt.scatter(y_true, y_pred, alpha=0.5)
        max_val = max(y_true.max(), y_pred.max()) * 1.05
        min_val = min(y_true.min(), y_pred.min()) * 0.95
        plt.plot([min_val, max_val], [min_val, max_val], "r-")

        plt.xlabel("実際の値")
        plt.ylabel("予測値")
        plt.title("予測値 vs 実際の値")
        plt.grid(True)
        plt.tight_layout()

        plt.savefig(f"{self.output_dir}/{save_name}_scatter.png", format="png", dpi=300)
        plt.close()

        # 時系列プロット（日付が指定されている場合）
        if dates is not None:
            plt.figure(figsize=figsize)

            # データフレームを作成
            plot_df = pd.DataFrame({"date": dates, "actual": y_true, "predicted": y_pred})

            plt.plot(plot_df["date"], plot_df["actual"], "b-", label="実際の値")
            plt.plot(plot_df["date"], plot_df["predicted"], "r--", label="予測値")
            plt.xlabel("日付")
            plt.ylabel("電力需要")
            plt.title("電力需要の時系列予測")
            plt.grid(True)
            plt.legend()

            # 日付の表示を調整
            plt.xticks(rotation=45)
            plt.tight_layout()

            plt.savefig(f"{self.output_dir}/{save_name}_timeseries.png", format="png", dpi=300)
            plt.close()

    def plot_evaluation_metrics(self, metrics: Dict[str, float], save_name: str = "model_metrics") -> None:
        """評価メトリクスを可視化する

        Args:
            metrics: メトリクスの辞書
            save_name: 保存するファイル名
        """
        plt.figure(figsize=(10, 6))

        # メトリクス名と値の取得
        names = list(metrics.keys())
        values = list(metrics.values())

        # バープロット
        colors = sns.color_palette("viridis", len(metrics))
        bars = plt.bar(names, values, color=colors)

        # バーの上に値を表示
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2.0, height, f"{height:.4f}", ha="center", va="bottom", rotation=0)

        plt.title("モデル評価メトリクス")
        plt.xlabel("メトリクス")
        plt.ylabel("値")
        plt.tight_layout()

        # ファイルに保存
        plt.savefig(f"{self.output_dir}/{save_name}.png", format="png", dpi=300)

        # CSVファイルにも保存
        pd.DataFrame([metrics]).to_csv(f"{self.output_dir}/{save_name}.csv", index=False)

        plt.close()

    def plot_feature_distributions(
        self,
        df: pd.DataFrame,
        columns: Union[List[str], None] = None,
        save_name: str = "feature_distributions",
    ) -> None:
        """特徴量の分布を可視化する

        Args:
            df: データフレーム
            columns: 可視化する列名のリスト（Noneの場合は全数値列）
            save_name: 保存するファイル名
        """
        # 数値型の列を抽出
        if columns is None:
            columns = df.select_dtypes(include=["int64", "float64"]).columns.tolist()

        # 特徴量の数に基づいてサブプロット数を決定
        n_features = len(columns)
        n_cols = 3
        n_rows = (n_features + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows))
        axes = axes.flatten() if n_rows > 1 else [axes] if n_cols == 1 else axes

        for i, col in enumerate(columns):
            if i < len(axes):
                sns.histplot(df[col], ax=axes[i], kde=True)
                axes[i].set_title(col)

        # 余ったサブプロットを非表示
        for i in range(n_features, len(axes)):
            if i < len(axes):
                axes[i].axis("off")

        plt.tight_layout()
        plt.savefig(f"{self.output_dir}/{save_name}.png", format="png", dpi=300)
        plt.close()

    def correlation_heatmap(
        self,
        df: pd.DataFrame,
        save_name: str = "correlation_heatmap",
        figsize: Union[Tuple[int, int], None] = None,
        cmap: str = "coolwarm",
    ) -> None:
        """相関ヒートマップを作成する

        Args:
            df: データフレーム
            save_name: 保存するファイル名
            figsize: グラフサイズ（Noneの場合は列数に基づいて自動設定）
            cmap: カラーマップ
        """
        # 数値列のみ抽出
        numeric_df = df.select_dtypes(include=["int64", "float64"])

        # 相関係数行列の計算
        corr = numeric_df.corr()

        # グラフサイズの決定
        if figsize is None:
            n = len(corr)
            figsize = (max(8, n * 0.5), max(6, n * 0.5))

        plt.figure(figsize=figsize)

        # ヒートマップ作成
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, cmap=cmap, annot=True, fmt=".2f", linewidths=0.5, cbar_kws={"shrink": 0.8})

        plt.title("特徴量間の相関ヒートマップ")
        plt.tight_layout()

        plt.savefig(f"{self.output_dir}/{save_name}.png", format="png", dpi=300)
        plt.close()


def load_model(model_tar_path: str) -> lgb.Booster:
    """model.tar.gz から model.pickle を取り出してモデルを返す
    Args:
        model_tar_path (str): モデルのtar.gzファイルのパス
    Returns:
        lgb.Booster: 学習済みモデル
    """
    # 解凍
    extract_dir = "/tmp/model"  # noqa: S108
    Path(extract_dir).mkdir(exist_ok=True)
    with tarfile.open(model_tar_path, "r:gz") as tar:
        tar.extractall(path=extract_dir)

    model_path = next(Path(extract_dir).rglob("model.pkl"))

    return joblib.load(model_path)


if __name__ == "__main__":
    logger.info("Starting visualization...")

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str)
    parser.add_argument("--test-path", type=str)
    parser.add_argument("--feature-names-path", type=str)
    parser.add_argument("--output-path", type=str)
    args = parser.parse_args()
    # コマンドライン引数の取得
    model_path = args.model_path
    test_data_path = args.test_path
    feature_names_path = args.feature_names_path
    output_path = args.output_path

    # モデルのロード
    model = load_model(model_path)

    # 可視化の実行
    visualizer = Visualizer(output_dir=output_path, model=model, feature_names_path=feature_names_path)

    # テストデータのロード
    X_test, y_true = visualizer.load_test_data(test_data_path)

    # 予測と評価
    y_pred = model.predict(X_test)
    metrics = visualizer.evaluate(y_true, y_pred)

    # 特徴量重要度の取得
    feature_importance = visualizer.get_feature_importance()

    # 特徴量重要度の可視化
    visualizer.plot_feature_importance(
        feature_importance,
        plot_features=min(20, len(feature_importance)),
        save_name="feature_importance",
    )

    # 予実の比較
    # dateカラムを作成
    X_test["date"] = pd.to_datetime(
        {
            "year": X_test["year"],
            "month": X_test["month"],
            "day": X_test["day"],
        },
    )
    visualizer.plot_prediction_vs_actual(
        y_true,
        y_pred,
        dates=X_test["date"],
        save_name="prediction_vs_actual",
    )
    # 評価メトリクスの可視化
    visualizer.plot_evaluation_metrics(metrics, save_name="model_metrics")

    # 特徴量の分布の可視化
    visualizer.plot_feature_distributions(
        X_test,
        columns=X_test.select_dtypes(include=["int64", "float64"]).columns.tolist(),
        save_name="feature_distributions",
    )

    # ヒートマップの作成
    visualizer.correlation_heatmap(X_test, save_name="correlation_heatmap")

    logger.info("finished visualization...")
