from pathlib import Path

import boto3
import sagemaker
import sagemaker.session
from botocore.client import BaseClient
from sagemaker import hyperparameters
from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionLessThanOrEqualTo
from sagemaker.workflow.functions import JsonGet
from sagemaker.workflow.parameters import ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.step_collections import RegisterModel
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

BASE_DIR = Path(__file__).parent


def get_sagemaker_client(region: str) -> BaseClient:
    """指定したregionのSageMakerクライアントを取得する関数"""
    boto_session = boto3.Session(region_name=region)
    return boto_session.client("sagemaker")


def get_session(region: str, default_bucket: str) -> sagemaker.session.Session:
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


def get_pipeline_custom_tags(new_tags: any, region: str, sagemaker_project_arn: str | None = None) -> list:
    try:
        sm_client = get_sagemaker_client(region)
        response = sm_client.list_tags(ResourceArn=sagemaker_project_arn)
        project_tags = response["Tags"]
        for project_tag in project_tags:
            new_tags.append(project_tag)
    except Exception as e:
        print(f"Error getting project tags: {e}")
    return new_tags


def get_pipeline(
    region: str,
    # sagemaker_project_arn: str | None = None,
    role: str | None = None,
    default_bucket: str | None = None,
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
    """
    # 1. SageMakerセッションの作成
    sagemaker_session = get_session(region, default_bucket)

    # 2. 入力データの設定
    weather_input_data = ParameterString(
        name="InputDataUrl",
        default_value=f"s3://power-forecasting-mlops-{environment}/data/weather_data.csv",
    )
    power_usage_input_data = ParameterString(
        name="PowerUsageInputDataUrl",
        default_value=f"s3://power-forecasting-mlops-{environment}/data/power_usage/",
    )

    # 3. 処理ステップの設定
    # load and processing step for feature engineering
    processing_instance_count = ParameterInteger(name="ProcessingInstanceCount", default_value=1)
    processing_instance_type = ParameterString(
        name="ProcessingInstanceType",
        default_value="ml.t3.medium",
    )

    # データをロードするステップ
    data_loader_script_processor = ScriptProcessor(
        image_uri="763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-processing:0.23-1-cpu-py3",
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
                destination="/opt/ml/processing/input_data",  # コンテナ内のマウント先
                input_name="weather_data",
            ),
            ProcessingInput(
                source=power_usage_input_data,
                destination="/opt/ml/processing/input_data",
                input_name="power_usage_data",
            ),
        ],
        outputs=[ProcessingOutput(output_name="merged_data", source="/opt/ml/processing/output")],
        code=Path.join(BASE_DIR, "data_loader.py"),
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
        ],
        outputs=[
            ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/test"),
        ],
        code=Path.join(BASE_DIR, "preprocess.py"),
        job_arguments=["--weather_input-data", weather_input_data, "--power_usage_input-data", power_usage_input_data],
    )

    # training step for generating model artifacts
    training_instance_type = ParameterString(name="TrainingInstanceType", default_value="ml.t3.medium")
    training_instance_count = ParameterInteger(name="TrainingInstanceCount", default_value=1)

    model_path = f"s3://{sagemaker_session.default_bucket()}/{base_job_prefix}/Train"
    train_model_id, train_model_version, train_scope = "lightgbm-regression-model", "*", "training"
    training_instance_type = "ml.t3.medium"
    lgbm_hyperparameters = hyperparameters.retrieve_default(
        model_id=train_model_id,
        model_version=train_model_version,
    )
    # 実行環境となるコンテナイメージを取得
    image_uri = sagemaker.image_uris.retrieve(
        region=region,
        framework=None,
        model_id=train_model_id,
        model_version=train_model_version,
        image_scope=train_scope,
        instance_type=training_instance_type,
    )
    lgbm_train = Estimator(
        image_uri=image_uri,
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
    evaluation_script_processor = ScriptProcessor(
        image_uri="763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-processing:0.23-1-cpu-py3",
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
                source=step_process.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
                input_name="test_data",
            ),
        ],
        outputs=[ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation")],
        code=Path.join(BASE_DIR, "evaluate.py"),
    )

    # 可視化ステップを追加
    visualization_script_processor = ScriptProcessor(
        image_uri="763104351884.dkr.ecr.us-west-2.amazonaws.com/sklearn-processing:0.23-1-cpu-py3",
        command=["python3"],
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/visualization",
        sagemaker_session=sagemaker_session,
        role=role,
    )

    step_visualization = ProcessingStep(
        name="VisualizeResults",
        processor=visualization_script_processor,
        inputs=[
            ProcessingInput(
                source=step_evaluate.properties.ProcessingOutputConfig.Outputs["evaluation"].S3Output.S3Uri,
                destination="/opt/ml/processing/evaluation",
                input_name="evaluation_data",
            ),
        ],
        outputs=[ProcessingOutput(output_name="visualizations", source="/opt/ml/processing/visualizations")],
        code=Path.join(BASE_DIR, "visualization.py"),
    )

    # モデル登録ステップを条件付きで追加する
    evaluation_report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )

    model_metrics = ModelMetrics(
        model_statistics=MetricsSource(
            s3_uri=step_evaluate.properties.ProcessingOutputConfig.Outputs["evaluation"].S3Output.S3Uri
            + "/evaluation.json",
            content_type="application/json",
        ),
    )

    step_register = RegisterModel(
        name="RegisterPowerForecastModel",
        estimator=lgbm_train,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["text/csv"],
        response_types=["text/csv"],
        # モデル利用者のために動作できるinstanceを記録しておくらしい
        inference_instances=["ml.t2.medium"],
        transform_instances=["ml.t2.medium"],
        model_package_group_name=model_package_group_name,
        approval_status="PendingManualApproval",
        model_metrics=model_metrics,
    )

    # モデル品質を評価し、分岐実行を行う条件ステップ
    cond_lte = ConditionLessThanOrEqualTo(
        left=JsonGet(
            step_name=step_evaluate.name,
            property_file=evaluation_report,
            json_path="regression_metrics.mse.value",
        ),
        right=999999.0,
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
