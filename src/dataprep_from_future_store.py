import subprocess
import sys

sys.path.append("/opt/ml/processing/deps")
# 必要なパッケージをその場でインストール
subprocess.run(
    [sys.executable, "-m", "pip", "install", "--quiet", "awswrangler", "omegaconf", "category-encoders"],
    check=True,
)

import argparse
import logging
import pickle
from pathlib import Path
from typing import Dict, Tuple, Union

import awswrangler as wr
import boto3
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from feature_encoder import FeatureEncoder

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def load_config(config_path: str) -> DictConfig:
    """設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス

    Returns:
        DictConfig: 設定情報
    """
    config = DictConfig(OmegaConf.load(config_path))
    return config


def parse_args() -> argparse.Namespace:
    """
    SageMakerから渡される引数をパースする

    Returns:
        argparse.Namespace: パースされた引数
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--glue-db", type=str)
    parser.add_argument("--glue-table", type=str)
    parser.add_argument("--region", type=str, default="ap-northeast-1")
    return parser.parse_args()


def load_data(args: argparse.Namespace, config: DictConfig) -> pd.DataFrame:
    """Offlineストアからデータを読み込む

    Args:
        args: コマンドライン引数

    Returns:
        pd.DataFrame: 読み込んだデータフレーム
    """
    query = f"""
        SELECT
            *
        FROM
        (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY record_id ORDER BY event_time DESC) AS latest
            FROM "{args.glue_db}"."{args.glue_table}"
        )
        WHERE date BETWEEN '{config.start_date}' AND '{config.end_date}' AND latest = 1
    """  # noqa: S608

    boto_session = boto3.Session(region_name=args.region)
    df = wr.athena.read_sql_query(
        query,
        database=args.glue_db,
        boto3_session=boto_session,
        s3_output="s3://power-forecast-athena-query-results-dev/",
        ctas_approach=True,
        workgroup="primary",
    )

    return df


def encode_features(
    df: pd.DataFrame,
    config: DictConfig,
) -> Tuple[pd.DataFrame, Dict[str, FeatureEncoder]]:
    """特徴量をエンコードする

    Args:
        df: 特徴量を含むデータフレーム
        config: 設定ファイルの内容

    Returns:
        Tuple[pd.DataFrame, Dict[str, FeatureEncoder]]: エンコードされたデータフレームとエンコーダーの辞書
    """
    # encoders_dictを必ず初期化
    encoders_dict = {}

    result_df = df.copy()

    if "encoders" in config:
        for params in config["encoders"]:
            if params["name"] not in encoders_dict:
                encoder = FeatureEncoder(**params)
                result_df = encoder.fit_transform(result_df)
                encoders_dict[params["name"]] = encoder
            else:
                encoder = encoders_dict[params["name"]]
                result_df = encoder.transform(result_df)

    return result_df, encoders_dict


def apply_encoders(df: pd.DataFrame, config: DictConfig) -> Tuple[pd.DataFrame, dict]:
    """エンコーダーを適用する
    Args:
        df: 特徴量を含むデータフレーム
        config: 設定ファイルの内容

    Returns:
        Tuple[pd.DataFrame, dict]: エンコード後データフレームとエンコーダー辞書
    """
    # 目的変数を一時的に除外
    target_col = "max_power"
    y = df.pop(target_col) if target_col in df.columns else None
    if config and "encoders" in config:
        df, encoders_dict = encode_features(df, config)
    else:
        encoders_dict = {}
    # 目的変数を先頭に戻す
    if y is not None:
        df = pd.concat([y, df], axis=1)
    return df, encoders_dict


def save_encoders(
    encoders_dict: Dict[str, FeatureEncoder],
    file_dir: Path,
    filename: str,
) -> None:
    """
    エンコーダを保存する関数

    Args:
        encoders_dict(Dict[str, FeatureEncoder]): エンコーダの辞書
        file_dir(Path): 保存先のディレクトリ
        file_name(str): 保存ファイル名
    """
    with Path(file_dir / filename).open("wb") as f:
        pickle.dump(encoders_dict, f)


def format_target_first(df: pd.DataFrame, target_col: str = "max_power") -> pd.DataFrame:
    """目的変数を明示的に最初のカラムに移動する
    Args:
        df: 入力データフレーム
        target_col: 目的変数のカラム名

    Returns:
        pd.DataFrame: 目的変数が最初のカラムに移動したデータフレーム

    Notes:
        awsのビルドインモデルを使用した場合先頭列に目的変数が必要なため列の順番を変更する
    """
    y = df.pop(target_col)
    return pd.concat([y, df], axis=1)


def train_test_split(
    df: pd.DataFrame,
    test_date: Union[str, None] = None,
    test_size: float = 0.2,
    date_col: str = "date",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    時系列データを訓練データとテストデータに分割する

    Args:
        df: 入力データフレーム
        test_date: テストデータの開始日付（例: '2024-10-01'）
                    指定がない場合は、test_sizeに基づいて分割
        test_size: テストデータの割合（test_dateが指定されていない場合に使用）

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 訓練データとテストデータ
    """
    df = format_target_first(df)
    # 日付でソート
    df_sorted = df.sort_values(date_col)

    if test_date:
        # 指定した日付で分割
        df_train = df_sorted[df_sorted[date_col] < test_date]
        df_test = df_sorted[df_sorted[date_col] >= test_date]
    else:
        # データ数に基づいて分割
        train_size = int(len(df_sorted) * (1 - test_size))
        df_train = df_sorted.iloc[:train_size]
        df_test = df_sorted.iloc[train_size:]

    # 不要なカラムを削除（athenaのクエリで取得したカラム）
    delete_cols = [date_col, "record_id", "event_time", "latest"]
    df_train = df_train.drop(columns=delete_cols).reset_index(drop=True)
    df_test = df_test.drop(columns=delete_cols).reset_index(drop=True)

    return df_train, df_test


def save_column_names(df: pd.DataFrame, output_path: str = "/opt/ml/processing/train/features.txt") -> None:
    """特徴量重要度のプロットのためカラム名を保存する

    Args:
        df: 入力データフレーム
        output_path: 出力パス
    """
    feature_names = df.columns.tolist()

    with Path(output_path).open("w") as f:
        for name in feature_names:
            f.write(f"{name}\n")


if __name__ == "__main__":
    logger.info("Starting processing data...")
    args = parse_args()
    base_dir = "/opt/ml/processing"
    config = load_config("/opt/ml/processing/deps/config.yaml")

    # データの読み込み
    df = load_data(args, config)

    # エンコーダーの適用
    processed_data, encoders_dict = apply_encoders(df, config)

    # データ分割
    train_data, test_data = train_test_split(processed_data, test_date=config.get("split_date"))
    # カラム名を保存
    save_column_names(train_data, output_path=f"{base_dir}/train/features.txt")

    # データの保存
    Path(f"{base_dir}/train").mkdir(parents=True, exist_ok=True)
    train_data.to_csv(f"{base_dir}/train/train.csv", index=False, header=False)
    save_encoders(
        encoders_dict,
        file_dir=Path(f"{base_dir}/train"),
        filename="encoders.pkl",
    )
    Path(f"{base_dir}/test").mkdir(parents=True, exist_ok=True)
    test_data.to_csv(f"{base_dir}/test/test.csv", index=False, header=False)
    logger.info("Finished processing data...")
