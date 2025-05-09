import json

import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def evaluate_model(y_true: pd.Series, y_pred: pd.Series, output_path: str) -> None:
    """モデルの評価を行い、結果をJSONファイルに保存する

    Args:
        y_true (pd.Series): 実際の値
        y_pred (pd.Series): 予測値
        output_path (str): 評価結果を保存するパス
    """
    metrics = {
        "mse": mean_squared_error(y_true, y_pred),
        "mae": mean_absolute_error(y_true, y_pred),
        "r2": r2_score(y_true, y_pred),
    }

    with open(output_path, "w") as f:
        json.dump(metrics, f)

    print(f"Evaluation metrics saved to {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--test_data", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()

    model_path = args.model
    test_data_path = args.test_data
    output_path = args.output

    # モデルのロード
    from joblib import load

    model = load(model_path)

    # テストデータのロード
    test_data = pd.read_csv(test_data_path)
    y_true = test_data["target"]
    X_test = test_data.drop(columns=["target"])

    # 予測と評価
    y_pred = model.predict(X_test)
    evaluate_model(y_true, y_pred, output_path)
