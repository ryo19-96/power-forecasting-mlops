# noqa: INP001
"""
model registryにダミーモデルを"PendingManualApproval"で登録するスクリプト
model pipelineを動作させなくてもその後の承認フロー確認用
"""

import boto3

sagemaker_client = boto3.client("sagemaker")
group_name = "PowerForecastPackageGroup"

model_pkg_response = sagemaker_client.create_model_package(
    ModelPackageGroupName=group_name,
    ModelPackageDescription="Dummy package",
    InferenceSpecification={
        "Containers": [
            {
                "Image": "763104351884.dkr.ecr.ap-northeast-1.amazonaws.com/tensorflow-inference-graviton:2.9.1-cpu-py38",  # noqa: E501
                "ModelDataUrl": "s3://power-forecasting-mlops-dev/test/model.tar.gz",
            },
        ],
        "SupportedContentTypes": ["text/csv"],
        "SupportedResponseMIMETypes": ["text/csv"],
    },
    ModelApprovalStatus="PendingManualApproval",
)

print("ModelPackage created:", model_pkg_response["ModelPackageArn"])
