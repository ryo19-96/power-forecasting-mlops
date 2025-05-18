import time

import boto3
from typing import Union
import sagemaker
from sagemaker.model import ModelPackage
from sagemaker.serverless.serverless_inference_config import ServerlessInferenceConfig


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


region = "ap-northeast-1"
role = "arn:aws:iam::163817410757:role/service-role/power-forecasting-role-dev"
default_bucket = "power-forecasting-mlops-dev"
sagemaker_session = get_session(region=region, default_bucket=default_bucket)

# ApprovedのモデルパッケージARNを取得
model_pkg_name = "PowerForecastPackageGroup"
sagemaker_client = boto3.client("sagemaker")
package_arn = sagemaker_client.list_model_packages(
    ModelPackageGroupName=model_pkg_name,
    ModelApprovalStatus="Approved",
    SortBy="CreationTime",
    SortOrder="Descending",
    MaxResults=1,
)["ModelPackageSummaryList"][0]["ModelPackageArn"]

# Serverless Endpointを作成
model = ModelPackage(role=role, model_package_arn=package_arn, sagemaker_session=sagemaker_session)

serverless_config = ServerlessInferenceConfig(memory_size_in_mb=2048, max_concurrency=5)

endpoint_name = f"power-forecast-serverless-{int(time.time())}"

predictor = model.deploy(serverless_inference_config=serverless_config, endpoint_name=endpoint_name)

print("Endpoint:", endpoint_name)
