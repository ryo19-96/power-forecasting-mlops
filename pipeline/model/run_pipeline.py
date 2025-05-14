from pipeline_aws import get_pipeline

region = "ap-northeast-1"
role = "arn:aws:iam::163817410757:role/service-role/AmazonSageMaker-ExecutionRole-20250507T172311"
default_bucket = "power-forecasting-mlops-dev"
pipeline_name = "PowerForecastPipeline"

pipeline = get_pipeline(
    region=region,
    role=role,
    default_bucket=default_bucket,
    pipeline_name=pipeline_name,
    environment="dev",
)

# 定義をSageMakerに登録
pipeline.upsert(role_arn=role)

# 実行
execution = pipeline.start()
print("Started pipeline execution:")
print(f"Execution ARN: {execution.arn}")

# actionsで完了を補足するために待機
execution.wait()

# 正常終了かチェック
if execution.describe()["PipelineExecutionStatus"] != "Succeeded":
    msg = "Pipeline execution failed."
    raise RuntimeError(msg)
else:
    print("Pipeline execution succeeded.")
