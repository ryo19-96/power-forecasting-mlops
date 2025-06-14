from pathlib import Path
from typing import Any, List, Union

import boto3
import sagemaker
import sagemaker.session
from botocore.client import BaseClient
from omegaconf import OmegaConf
from sagemaker.inputs import TrainingInput
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.sklearn.estimator import SKLearn
from sagemaker.sklearn.model import SKLearnModel
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionLessThanOrEqualTo
from sagemaker.workflow.functions import Join, JsonGet
from sagemaker.workflow.parameters import ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.step_collections import RegisterModel
from sagemaker.workflow.steps import CacheConfig, ProcessingStep, TrainingStep

# srcディレクトリのパスを取得
BASE_DIR = Path(__file__).parent.parent.parent / "src"


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
    enable_cache: bool,
    role: Union[str, None] = None,
    default_bucket: Union[str, None] = None,
    model_package_group_name: str = "PowerForecastPackageGroup",
    pipeline_name: str = "PowerForecastPipeline",
    base_job_prefix: str = "PowerForecast",
    environment: str = "dev",
    pipeline_config: Union[OmegaConf, None] = None,
) -> Pipeline:
    """パイプラインを取得する関数

    Args:
        region (str): AWSリージョン
        enable_cache (bool): キャッシュを有効にするかどうか
        sagemaker_project_arn (str, optional): SageMakerプロジェクトのARN
        role (str, optional): IAMロール
        default_bucket (str, optional): デフォルトバケット名
        model_package_group_name (str, optional): モデルパッケージグループ名
        pipeline_name (str, optional): パイプライン名
        base_job_prefix (str, optional): ジョブプレフィックス
        environment (str, optional): 環境名（dev, prodなど）
        pipeline_config (OmegaConf, optional): パイプライン設定（デフォルトNone）

    Returns:
        Pipeline: SageMakerパイプラインオブジェクト

    Nones:
        sagemaker_project_arn: str | None = None が後で必要になる？
    """
    # SageMakerセッションの作成
    sagemaker_session = get_session(region, default_bucket)
    cache_config = CacheConfig(enable_caching=enable_cache, expire_after="P30D")

    # 処理ステップの設定
    processing_instance_count = ParameterInteger(
        name="ProcessingInstanceCount",
        default_value=pipeline_config.get("processing_instance_count", 1),
    )
    processing_instance_type = ParameterString(
        name="ProcessingInstanceType",
        default_value=pipeline_config.get("processing_instance_type", "ml.t3.medium"),
    )
    image_uri = sagemaker.image_uris.retrieve(
        framework="sklearn",
        region=region,
        version="0.23-1",
        py_version="py3",
        instance_type="ml.t3.medium",
    )

    # === 特徴量エンジニアリングのステップ ===
    emr_output_uri = ParameterString(
        name="EMROutputUri",
        default_value=f"s3://power-forecasting-processed-data-{environment}/",
    )
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
                source=emr_output_uri,
                destination="/opt/ml/processing/input_data/",  # コンテナ内のマウント先
                input_name="merged_data",
            ),
            ProcessingInput(source=str(BASE_DIR), destination="/opt/ml/processing/deps"),
        ],
        outputs=[
            ProcessingOutput(output_name="extract_features", source="/opt/ml/processing/extract_features"),
        ],
        code=str(BASE_DIR / "preprocess.py"),
        job_arguments=[
            "--input-data",
            "/opt/ml/processing/input_data/",
        ],
        cache_config=cache_config,
    )
    # === Feature Storeへの登録ステップ ===
    feature_group_name_param = ParameterString("FeatureGroupName", default_value="power_forecast_features")

    feature_ingest_proc = ScriptProcessor(
        image_uri=image_uri,
        command=["python3"],
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/ingest-feature",
        sagemaker_session=sagemaker_session,
        role=role,
    )

    step_ingest = ProcessingStep(
        name="IngestToFeatureStore",
        processor=feature_ingest_proc,
        inputs=[
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs["extract_features"].S3Output.S3Uri,
                destination="/opt/ml/processing/extract_features",
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="offline_uri",
                source="/opt/ml/processing/offline_uri",
            ),
        ],
        code=str(BASE_DIR / "ingest_feature_store.py"),
        job_arguments=[
            "--feature-group-name",
            feature_group_name_param,
            "--region",
            region,
        ],
        cache_config=cache_config,
    )

    # === train, testデータの準備ステップ ===
    glue_db = ParameterString("glue_db", default_value="power_features_db")
    glue_table = ParameterString("glue_table", default_value="power_forecast_features")

    dataprep_proc = ScriptProcessor(
        image_uri=image_uri,
        command=["python3"],
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/dataprep",
        role=role,
        sagemaker_session=sagemaker_session,
    )
    step_dataprep = ProcessingStep(
        name="DataPrepFromFeatureStore",
        processor=dataprep_proc,
        # offline storeメタ(基本的に不要だがpipeline DAGで表示されるように意図的にinputを書く)
        inputs=[
            ProcessingInput(
                source=step_ingest.properties.ProcessingOutputConfig.Outputs["offline_uri"].S3Output.S3Uri,
                destination="/opt/ml/processing/offline_meta",
            ),
            ProcessingInput(source=str(BASE_DIR), destination="/opt/ml/processing/deps"),
        ],
        outputs=[
            ProcessingOutput(source="/opt/ml/processing/train", output_name="train"),
            ProcessingOutput(source="/opt/ml/processing/test", output_name="test"),
        ],
        code=str(BASE_DIR / "dataprep_from_future_store.py"),
        job_arguments=[
            "--glue-db",
            glue_db,
            "--glue-table",
            glue_table,
            "--region",
            region,
        ],
        cache_config=cache_config,
    )

    # === モデルのトレーニングステップ ===
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

    # SKLearn estimatorを作成
    train_estimator = SKLearn(
        entry_point="train.py",
        source_dir=str(BASE_DIR),  # srcディレクトリを指定
        role=role,
        instance_type=training_instance_type,
        instance_count=1,  # SKLearnは並列学習をサポートしていないので"1"固定
        framework_version="1.2-1",
        base_job_name=f"{base_job_prefix}/train",
        hyperparameters={"n_estimators": 100},
        output_path=model_path,
        py_version="py3",
    )

    step_train = TrainingStep(
        name="TrainModel",
        estimator=train_estimator,
        inputs={
            "train": TrainingInput(
                s3_data=step_dataprep.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                content_type="text/csv",
            ),
        },
        cache_config=cache_config,
    )

    # デプロイ時に必要なイメージURI
    sklearn_inf_image = sagemaker.image_uris.retrieve(
        framework="sklearn",
        region=region,
        version="1.2-1",
        py_version="py3",
        instance_type="ml.m5.large",
        image_scope="inference",
    )

    model = SKLearnModel(
        image_uri=sklearn_inf_image,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        role=role,
        entry_point="inference.py",
        source_dir="src",
        sagemaker_session=sagemaker_session,
    )

    # === モデルの評価ステップ ===
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
                source=step_dataprep.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                destination="/opt/ml/processing/train",
                input_name="train_data",
            ),
            ProcessingInput(
                source=step_dataprep.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
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
        cache_config=cache_config,
    )

    # === 可視化ステップ ===
    visualization_script_processor = ScriptProcessor(
        image_uri=image_uri,
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
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
                input_name="model",
            ),
            ProcessingInput(
                source=step_dataprep.properties.ProcessingOutputConfig.Outputs["train"].S3Output.S3Uri,
                destination="/opt/ml/processing/train",
                input_name="train_data",
            ),
            ProcessingInput(
                source=step_dataprep.properties.ProcessingOutputConfig.Outputs["test"].S3Output.S3Uri,
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
        cache_config=cache_config,
    )

    # === モデル登録ステップを条件付きで追加 ===
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
        model=model,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["application/json"],
        response_types=["application/json"],
        inference_instances=["ml.m5.large"],
        transform_instances=["ml.m5.large"],
        model_package_group_name=model_package_group_name,
        approval_status="PendingManualApproval",
        model_metrics=model_metrics,
    )

    # === モデル品質を評価し、分岐実行を行う条件ステップ ===
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
            feature_group_name_param,
            emr_output_uri,
            glue_db,
            glue_table,
        ],
        steps=[step_process, step_ingest, step_dataprep, step_train, step_evaluate, step_visualization, step_cond],
        sagemaker_session=sagemaker_session,
    )
    return pipeline
