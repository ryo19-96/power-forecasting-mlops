from pathlib import Path
from typing import Any, List, Union

import boto3
import sagemaker
import sagemaker.session
from botocore.client import BaseClient
from omegaconf import OmegaConf
from sagemaker import hyperparameters
from sagemaker.inputs import TrainingInput
from sagemaker.jumpstart.estimator import JumpStartEstimator
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionLessThanOrEqualTo
from sagemaker.workflow.functions import Join, JsonGet
from sagemaker.workflow.parameters import ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.step_collections import RegisterModel
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"
config = OmegaConf.load(CONFIG_PATH)
pipeline_config = config.get("pipeline", {})


def get_sagemaker_client(region: str) -> BaseClient:
    """指定したregionのSageMakerクライアントを取得する関数"""
    boto_session = boto3.Session(region_name=region)
    return boto_session.client("sagemaker")


def get_session(region: str, default_bucket: Union[str, None]) -> sagemaker.session.Session:
    """セッションを取得する関数（接続ハブのような役割を果たす）
    Args:
        region (str): AWSリージョン
        default_bucket (str): デフォルトバケット名
    Returns:
        sagemaker.session.Session: SageMakerセッションオブジェクト
    """

    boto_session = boto3.Session(region_name=region)

    sagemaker_client = boto_session.client("sagemaker")
    runtime_client = boto_session.client("sagemaker-runtime")
    return sagemaker.session.Session(
        boto_session=boto_session,
        sagemaker_client=sagemaker_client,
        sagemaker_runtime_client=runtime_client,
        default_bucket=default_bucket,
    )


def get_pipeline_custom_tags(new_tags: Any, region: str, sagemaker_project_arn: Union[str, None] = None) -> List:
    try:
        sm_client = get_sagemaker_client(region)
        response = sm_client.list_tags(ResourceArn=sagemaker_project_arn)
        project_tags = response["Tags"]
        for project_tag in project_tags:
            new_tags.append(project_tag)
    except Exception as e:
        msg = f"Error getting project tags: {e}"
        raise RuntimeError(msg)
    return new_tags


def get_pipeline(
    region: str,
    role: Union[str, None] = None,
    default_bucket: Union[str, None] = None,
    model_package_group_name: str = "PowerForecastPackageGroup",
    pipeline_name: str = "PowerForecastPipeline",
    base_job_prefix: str = "PowerForecast",
    environment: str = "dev",
) -> Pipeline:
    """パイプラインを取得する関数

    Args:
        region (str): AWSリージョン
        sagemaker_project_arn (str, optional): SageMakerプロジェクトのARN
        role (str, optional): IAMロール
        default_bucket (str, optional): デフォルトバケット名
        model_package_group_name (str, optional): モデルパッケージグループ名
        pipeline_name (str, optional): パイプライン名
        base_job_prefix (str, optional): ジョブプレフィックス
        environment (str, optional): 環境名（dev, prodなど）

    Returns:
        Pipeline: SageMakerパイプラインオブジェクト

    Nones:
        sagemaker_project_arn: str | None = None が後で必要になる？
    """
    # 1. SageMakerセッションの作成
    sagemaker_session = get_session(region, default_bucket)

    # 2. 入力データの設定
    weather_input_data = ParameterString(
        name="InputDataUrl",
        default_value=pipeline_config.get(
            "weather_data_s3",
            f"s3://power-forecasting-mlops-{environment}/data/weather_data.csv",
        ),
    )
    power_usage_input_data = ParameterString(
        name="PowerUsageInputDataUrl",
        default_value=pipeline_config.get(
            "power_usage_s3",
            f"s3://power-forecasting-mlops-{environment}/data/power_usage/",
        ),
    )

    # 3. 処理ステップの設定
    # load and processing step for feature engineering
    processing_instance_count = ParameterInteger(
        name="ProcessingInstanceCount",
        default_value=pipeline_config.get("processing_instance_count", 1),
    )
    processing_instance_type = ParameterString(
        name="ProcessingInstanceType",
        default_value=pipeline_config.get("processing_instance_type", "ml.t3.medium"),
    )

    # データをロードして結合するステップ
    image_uri = sagemaker.image_uris.retrieve(
        framework="sklearn",
        region="ap-northeast-1",
        version="0.23-1",
        py_version="py3",
        instance_type="ml.t3.medium",
    )
    data_loader_script_processor = ScriptProcessor(
        image_uri=image_uri,
        command=["python3"],
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/data-loader",
        sagemaker_session=sagemaker_session,
        role=role,
    )

    step_data_loader = ProcessingStep(
        name="LoadData",
        processor=data_loader_script_processor,
        inputs=[
            ProcessingInput(
                source=weather_input_data,
                destination="/opt/ml/processing/input/weather",  # コンテナ内のマウント先
                input_name="weather_data",
            ),
            ProcessingInput(
                source=power_usage_input_data,
                destination="/opt/ml/processing/input/power_usage",
                input_name="power_usage_data",
            ),
        ],
        outputs=[ProcessingOutput(output_name="merged_data", source="/opt/ml/processing/output")],
        code=str(BASE_DIR / "data_loader.py"),
        job_arguments=[
            "--weather-input-data",
            "/opt/ml/processing/input/weather/weather_data.csv",
            "--power-usage-input-data",
            "/opt/ml/processing/input/power_usage/",
        ],
    )

    # 特徴量エンジニアリングのステップ
    sklearn_processor = SKLearnProcessor(
        framework_version="0.23-1",
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/sklearn-preprocess",
        sagemaker_session=sagemaker_session,
        role=role,
    )

    step_process = ProcessingStep(
        name="PreprocessData",
        processor=sklearn_processor,
        inputs=[
            ProcessingInput(
                source=step_data_loader.properties.ProcessingOutputConfig.Outputs["merged_data"].S3Output.S3Uri,
                destination="/opt/ml/processing/input_data",
                input_name="merged_data",
            ),
            ProcessingInput(source=str(BASE_DIR), destination="/opt/ml/processing/deps"),
        ],
        outputs=[
            ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/test"),
        ],
        code=str(BASE_DIR / "preprocess.py"),
        job_arguments=[
            "--input-data",
            "/opt/ml/processing/input_data/merged_data.pkl",
        ],
    )

    # training step for generating model artifacts
    training_instance_type = ParameterString(
        name="TrainingInstanceType",
        default_value=pipeline_config.get("training_instance_type", "ml.m5.large"),
    )
    training_instance_count = ParameterInteger(
        name="TrainingInstanceCount",
        default_value=pipeline_config.get("training_instance_count", 1),
    )

    model_path = f"s3://{sagemaker_session.default_bucket()}/{base_job_prefix}/Train"
    train_model_id, train_model_version = "lightgbm-regression-model", "*"
    lgbm_hyperparameters = hyperparameters.retrieve_default(
        model_id=train_model_id,
        model_version=train_model_version,
    )
    lgbm_hyperparameters["metric"] = "auto"
    # 実行環境となるコンテナイメージを取得
    # jumpstartのビルトインモデルを使用する
    lgbm_train = JumpStartEstimator(
        model_id=train_model_id,
        model_version=train_model_version,
        instance_type=training_instance_type,
        instance_count=training_instance_count,
        output_path=model_path,
        base_job_name=f"{base_job_prefix}/train",
        sagemaker_session=sagemaker_session,
        role=role,
        hyperparameters=lgbm_hyperparameters,
    )

    step_train = TrainingStep(
        name="TrainModel",
        estimator=lgbm_train,
        inputs={
            "train": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                content_type="text/csv",
            ),
        },
    )

    # モデルの評価ステップを追加
    # 評価の結果をevaluation.jsonに出力する
    evaluation_report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )

    evaluation_script_processor = ScriptProcessor(
        image_uri=image_uri,
        command=["python3"],
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/evaluate",
        sagemaker_session=sagemaker_session,
        role=role,
    )

    step_evaluate = ProcessingStep(
        name="EvaluateModel",
        processor=evaluation_script_processor,
        inputs=[
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
                input_name="model",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                destination="/opt/ml/processing/train",
                input_name="train_data",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
                input_name="test_data",
            ),
        ],
        outputs=[ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation")],
        code=str(BASE_DIR / "evaluate.py"),
        property_files=[evaluation_report],
        job_arguments=[
            "--model-path",
            "/opt/ml/processing/model/model.tar.gz",
            "--test-path",
            "/opt/ml/processing/test/test.csv",
            "--feature-names-path",
            "/opt/ml/processing/train/features.txt",
            "--output-path",
            "/opt/ml/processing/evaluation",
        ],
    )

    # 可視化ステップを追加
    visualization_script_processor = ScriptProcessor(
        image_uri=image_uri,
        command=["python3"],
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/visualization",
        sagemaker_session=sagemaker_session,
        role=role,
    )
    # UI用の画像を出すのか、HTMLレポートを作るのか、ログだけなのかなど、可視化の目的と出力フォーマットを後で
    # はっきりさせておくと良い。S3Uri + ファイル名 で保存場所を明確にしておくと、Looker や BIツールとの連携も楽
    step_visualization = ProcessingStep(
        name="VisualizeResults",
        processor=visualization_script_processor,
        inputs=[
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
                input_name="model",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                destination="/opt/ml/processing/train",
                input_name="train_data",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
                input_name="test_data",
            ),
        ],
        outputs=[ProcessingOutput(output_name="visualizations", source="/opt/ml/processing/visualizations")],
        code=str(BASE_DIR / "visualization.py"),
        job_arguments=[
            "--model-path",
            "/opt/ml/processing/model/model.tar.gz",
            "--test-path",
            "/opt/ml/processing/test/test.csv",
            "--feature-names-path",
            "/opt/ml/processing/train/features.txt",
            "--output-path",
            "/opt/ml/processing/visualizations",
        ],
    )

    # モデル登録ステップを条件付きで追加する
    evaluation_json_uri = Join(
        on="/",
        values=[
            step_evaluate.properties.ProcessingOutputConfig.Outputs["evaluation"].S3Output.S3Uri,
            "evaluation.json",
        ],
    )

    model_metrics = ModelMetrics(
        model_statistics=MetricsSource(
            s3_uri=evaluation_json_uri,
            content_type="application/json",
        ),
    )

    step_register = RegisterModel(
        name="RegisterPowerForecastModel",
        estimator=lgbm_train,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["text/csv"],
        response_types=["text/csv"],
        inference_instances=["ml.m5.large"],
        transform_instances=["ml.m5.large"],
        model_package_group_name=model_package_group_name,
        approval_status="Approved",
        model_metrics=model_metrics,
    )

    # モデル品質を評価し、分岐実行を行う条件ステップ
    cond_lte = ConditionLessThanOrEqualTo(
        left=JsonGet(
            step_name=step_evaluate.name,
            property_file=evaluation_report,
            json_path="regression_metrics.mse.value",
        ),
        right=pipeline_config.get("mse_threshold", 10000.0),
    )

    step_cond = ConditionStep(
        name="CheckMSEPowerForecastEvaluation",
        conditions=[cond_lte],
        if_steps=[step_register],
        else_steps=[],
    )

    # パイプラインインスタンスの更新
    pipeline = Pipeline(
        name=pipeline_name,
        parameters=[
            processing_instance_type,
            processing_instance_count,
            training_instance_type,
            training_instance_count,
            weather_input_data,
            power_usage_input_data,
        ],
        steps=[step_data_loader, step_process, step_train, step_evaluate, step_visualization, step_cond],
        sagemaker_session=sagemaker_session,
    )
    return pipeline
