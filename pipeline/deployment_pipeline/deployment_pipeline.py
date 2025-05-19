from datetime import datetime
from pathlib import Path
from typing import Union
from zoneinfo import ZoneInfo

import boto3
import botocore.client
import sagemaker
import yaml
from sagemaker.workflow.lambda_step import Lambda, LambdaStep
from sagemaker.workflow.parameters import ParameterString
from sagemaker.workflow.pipeline import Pipeline


def load_config(config_path: Union[str, Path]) -> dict:
    """設定ファイルの読み込み
    Args:
        config_path (Union[str, Path]): 設定ファイルのパス
    Returns:
        dict: 設定内容を格納した辞書
    """
    with Path(config_path).open("r") as f:
        return yaml.safe_load(f)


def get_session(region: str, default_bucket: Union[str, None]) -> sagemaker.session.Session:
    """SageMakerセッションを作成
    Args:
        region (str): AWSリージョン
        default_bucket (Union[str, None]): デフォルトのS3バケット名
    Returns:
        sagemaker.session.Session: SageMakerセッション
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


def get_latest_approved_model_package(sagemaker_client: botocore.client, model_pkg_name: str) -> str:
    """最新の承認済みモデルパッケージARNを取得する
    Args:
        sagemaker_client: SageMakerクライアント
        model_pkg_name (str): モデルパッケージグループ名
    Returns:
        str: モデルパッケージARN
    """
    response = sagemaker_client.list_model_packages(
        ModelPackageGroupName=model_pkg_name,
        ModelApprovalStatus="Approved",
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=1,
    )
    return response["ModelPackageSummaryList"][0]["ModelPackageArn"]


run_time = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d-%H%M%S")

config_path = Path(__file__).parent.parent / "config.yaml"
config = load_config(config_path)
run_config = config.get("run", {})
pipeline_config = config.get("pipeline", {})

region = run_config.get("region", "ap-northeast-1")
role = run_config.get("deployment_role")
default_bucket = run_config.get("default_bucket")
environment = run_config.get("environment", "dev")
model_package_name = "PowerForecastPackageGroup"

# sessionを作成
sagemaker_session = get_session(region=region, default_bucket=default_bucket)
# Approved になったARN
sagemaker_client = boto3.client("sagemaker", region_name=region)
package_arn = get_latest_approved_model_package(sagemaker_client, model_package_name)
model_package_arn = ParameterString("ModelPackageArn", default_value=package_arn)
endpoint_name = ParameterString("EndpointName", default_value=f"power-forecast-srvless-{run_time}")


deploy_lambda = Lambda(
    function_name="deploy-step",
    script="deploy_step.py",
    handler="deploy_step.lambda_handler",
    execution_role_arn=role,
    # TODO: 以下の渡し方だとエラーは出ないが、Lambdaの環境変数に渡せてない。今回はコンソール上から追加した
    environment={
        "Variables": {
            "DEPLOYMENT_ROLE": role,
            "REGION": region,
        },
    },
)

deploy_step = LambdaStep(
    name="DeployServerlessEndpoint",
    lambda_func=deploy_lambda,
    inputs={
        "model_package_arn": model_package_arn,
        "endpoint_name": endpoint_name,
    },
)

pipeline = Pipeline(
    name="PowerForecastDeploymentPipeline",
    parameters=[model_package_arn, endpoint_name],
    steps=[deploy_step],
    sagemaker_session=sagemaker_session,
)

pipeline.upsert(role_arn=role)
