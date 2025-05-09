import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


class Visualizer:
    """モデルの評価や特徴量の可視化を行うクラス"""

    def __init__(self, output_dir: str = "./output") -> None:
        """
        Args:
            output_dir: 出力ディレクトリ
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def plot_feature_importance(
        self,
        feature_importance_df: pd.DataFrame,
        plot_features: int = 20,
        save_name: str = "feature_importance",
        figsize: tuple[int, int] = None,
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
        y_true: pd.Series | np.ndarray,
        y_pred: np.ndarray,
        dates: pd.Series | None = None,
        save_name: str = "prediction_vs_actual",
        figsize: tuple[int, int] = (15, 8),
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

    def plot_evaluation_metrics(self, metrics: dict[str, float], save_name: str = "model_metrics") -> None:
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
        self, df: pd.DataFrame, columns: list[str] = None, save_name: str = "feature_distributions",
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
        figsize: tuple[int, int] = None,
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation_data", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()

    evaluation_data_path = args.evaluation_data
    output_path = args.output

    # 評価データのロード
    evaluation_data = pd.read_json(evaluation_data_path)

    # 可視化の実行
    visualizer = Visualizer(output_dir=output_path)
    visualizer.plot_evaluation_metrics(evaluation_data.to_dict(), save_name="model_metrics")
