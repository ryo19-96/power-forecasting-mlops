import time
from pathlib import Path
from typing import Union

import boto3
import botocore.client
import sagemaker
import yaml
from sagemaker.model import ModelPackage
from sagemaker.serverless.serverless_inference_config import ServerlessInferenceConfig


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
    """SageMakerセッションを作成する関数

    Args:
        region (str): AWSリージョン
        default_bucket (Union[str, None]): デフォルトのS3バケット名

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


def deploy_endpoint(model_package_arn: str, role: str, sagemaker_session: sagemaker.session.Session) -> str:
    """デプロイする関数

    Args:
        model_package_arn(str): モデルパッケージのARN
        role(str): SageMaker用のIAMロール
        sagemaker_session(sagemaker.session.Session): SageMakerセッションオブジェクト

    Returns:
        str: デプロイされたエンドポイント名
    """
    model = ModelPackage(role=role, model_package_arn=model_package_arn, sagemaker_session=sagemaker_session)

    serverless_config = ServerlessInferenceConfig(memory_size_in_mb=2048, max_concurrency=5)

    endpoint_name = f"power-forecast-serverless-{int(time.time())}"

    model.deploy(serverless_inference_config=serverless_config, endpoint_name=endpoint_name)

    return endpoint_name


# 設定ファイルの読み込み
config_path = Path(__file__).parent.parent / "config.yaml"
config = load_config(config_path)
run_config = config.get("run", {})

region = run_config.get("region", "ap-northeast-1")
role = run_config.get("role")
default_bucket = run_config.get("default_bucket")
model_package_name = "PowerForecastPackageGroup"

# SageMakerセッション作成
sagemaker_session = get_session(region=region, default_bucket=default_bucket)

# 最新の承認済みモデルパッケージARNを取得
sagemaker_client = boto3.client("sagemaker", region_name=region)
package_arn = get_latest_approved_model_package(sagemaker_client, model_package_name)

# デプロイ
endpoint_name = deploy_endpoint(model_package_arn=package_arn, role=role, sagemaker_session=sagemaker_session)

print("Endpoint:", endpoint_name)
