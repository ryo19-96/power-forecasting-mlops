# Power-Forecasting-MLOps

## 概要

MLOpsの学習および実践を目的として、気象データと過去の電力使用実績を用いた機械学習モデルによる電力需要予測パイプラインを構築しました。
前処理、学習、評価、可視化、モデル登録といった一連のプロセスを AWS SageMaker Pipeline 上に構築し、データ・成果物の保存には S3、インフラの構成管理には Terraform を用いて、クラウドネイティブな MLOps 運用を一貫して自動化・管理しています。

---

## パイプライン全体像

![パイプラインimage](images/architecture_diagram.svg)

| ステップ                                   | 内容                               |
| :----------------------------------------- | :--------------------------------- |
| `LoadData`                                 | データのロード                     |
| `PreprocessData`                           | 前処理・特徴量エンジニアリング     |
| `TrainModel`                               | モデル学習                         |
| `VisualizeResults`                         | モデル性能・変数重要度などの可視化 |
| `EvaluateModel`                            | モデル評価                         |
| `CheckMSEPowerForecastEvaluation`          | モデル性能の確認                   |
| `RegisterPowerForecastModel-RegisterModel` | モデルの登録                       |

---

## ディレクトリ構成

| ディレクトリ/ファイル | 内容                             |
| :-------------------- | :------------------------------- |
| `data/`               | 入力データ（ローカル使用時）     |
| `pipeline/`           | モデル・前処理・パイプライン実装 |
| `terraform/`          | AWSインフラ構成（IaC）           |
| `docs/`               | ドキュメント                     |
| `pyproject.toml`      | Pythonプロジェクト管理（Poetry） |
| `makefile`            | 各種コマンド自動化（ruff）       |

---

## 主要ファイル・機能

| ファイル名                          | 役割                         |
| :---------------------------------- | :--------------------------- |
| `data/weather_data.csv`             | 気象データ                   |
| `data/power_usage/`                 | 月別電力使用量データ         |
| `pipeline/model/preprocess.py`      | データ前処理                 |
| `pipeline/model/feature_encoder.py` | 特徴量エンジニアリング       |
| `pipeline/model/model.py`           | モデル定義・学習             |
| `pipeline/model/evaluate.py`        | モデル評価                   |
| `pipeline/model/visualization.py`   | 結果可視化                   |
| `pipeline/model/run_pipeline.py`    | 一連のパイプライン実行       |
| `pipeline/model/output/`            | モデル・評価・可視化出力     |
| `terraform/`                        | AWSリソース管理（S3, IAM等） |

---



## セットアップ手順

1. 依存パッケージのインストール
   ```sh
   poetry install
   ```

2. パイプライン実行
   ```sh
   poetry run python pipeline/model/run_pipeline.py
   ```

3. AWSリソース構築（必要に応じて）
   ```sh
   cd terraform
   terraform init
   terraform apply
   ```

---

## 出力例

| ファイル名                            | 内容例                     |
| :------------------------------------ | :------------------------- |
| `model_metrics.png`                   | モデル評価指標の可視化     |
| `feature_importance.png`              | 特徴量重要度グラフ         |
| `prediction_vs_actual_timeseries.png` | 予測値と実測値の時系列比較 |

---


## Next Steps

### 1. 推論APIの構築
- SageMaker Serverless Inference による軽量のエンドポイント運用
- API を通じて外部サービスから予測値を取得可能にする

### 2. モデルの自動デプロイの実装（CD）
- パイプライン完了後、モデルが "Approved" 状態であることを確認 → APIエンドポイントとして自動デプロイ

### 3.  監視・通知機能の追加
- パイプライン失敗時やモデル精度劣化時にSlackで通知
- モデル精度やデータドリフトの継続的モニタリング（SageMaker Model Monitor）

### 4. パイプラインのパラメータ化と環境分離
- Pipelineの引数としてインスタンスタイプやメトリクス閾値をyamlなどで外部設定化できるようにする
- dev/prod などの環境ごとにバケット・エンドポイントを切り替える仕組みの導入する

### 5.  コスト最適化（FinOps）
- S3やログのライフサイクル設定などのストレージコスト最適化

### 6. Feature Storeの導入
- 特徴量管理の一元化

---