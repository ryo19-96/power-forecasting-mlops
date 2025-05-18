import time

import boto3
from pipeline_aws import get_session
from sagemaker.model import ModelPackage
from sagemaker.serverless.serverless_inference_config import ServerlessInferenceConfig

region = "ap-northeast-1"
role = "arn:aws:iam::163817410757:role/service-role/AmazonSageMaker-ExecutionRole-20250507T172311"
default_bucket = "power-forecasting-mlops-dev"
sagemaker_session = get_session(region=region, default_bucket=default_bucket)

# ApprovedのモデルパッケージARNを取得
model_pkg_name = "PowerForecastPackageGroup"
sagemaker_client = boto3.client("sagemaker")
pkg_arn = sagemaker_client.list_model_packages(
    ModelPackageGroupName=model_pkg_name,
    ModelApprovalStatus="Approved",
    SortBy="CreationTime",
    SortOrder="Descending",
    MaxResults=1,
)["ModelPackageSummaryList"][0]["ModelPackageArn"]

# Serverless Endpointを作成
model = ModelPackage(role=role, model_package_arn=pkg_arn, sagemaker_session=sagemaker_session)

serverless_config = ServerlessInferenceConfig(memory_size_in_mb=2048, max_concurrency=5)

endpoint_name = f"power-forecast-serverless-{int(time.time())}"

predictor = model.deploy(serverless_inference_config=serverless_config, endpoint_name=endpoint_name)

print("Endpoint:", endpoint_name)
