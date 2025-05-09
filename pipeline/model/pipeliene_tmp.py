from pathlib import Path

import boto3
import sagemaker
import sagemaker.session
from botocore.client import BaseClient
from sagemaker import hyperparameters
from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.parameters import ParameterInteger, ParameterString
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


def get_pipeline_custom_tags(new_tags, region: str, sagemaker_project_arn: str = None) -> list:
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
    region,
    sagemaker_project_arn=None,
    role=None,
    default_bucket=None,
    model_package_group_name="PowerForecastPackageGroup",
    pipeline_name="PowerForecastPipeline",
    base_job_prefix="PowerForecast",
    environment="dev",
):
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

    # processing step for evaluation
