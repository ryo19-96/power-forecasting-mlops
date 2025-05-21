import json
import os

import boto3
from fastapi import FastAPI, HTTPException

from inference_api.schemas import PredictRequest, PredictResponse

app = FastAPI(title="Power Forecast Proxy")

# エンドポイント名とリージョンを環境変数から読み込む
ENDPOINT_NAME = os.getenv("SAGEMAKER_ENDPOINT_NAME", "endpoint-name")
REGION = os.getenv("AWS_REGION", "ap-northeast-1")
runtime_client = boto3.client("sagemaker-runtime", region_name=REGION)


# getだとボディが取れないのでpostで受け取る
@app.post("/predict")
def predict(request: PredictRequest) -> PredictResponse:
    try:
        payload = request.dict()
        # HTTPレスポンス
        response = runtime_client.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType="application/json",
            Body=json.dumps(payload),
        )
        result = json.loads(response["Body"].read().decode("utf-8"))
        return PredictResponse(predictions=result["predictions"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
