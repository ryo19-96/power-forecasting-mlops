import os

from sagemaker.processing import ProcessingOutput
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.steps import ProcessingStep

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


sklearn_processor = SKLearnProcessor(
    framework_version="0.23-1",
    instance_type=processing_instance_type,
    instance_count=processing_instance_count,
    base_job_name=f"{base_job_prefix}/sklearn-abalone-preprocess",
    sagemaker_session=sagemaker_session,
    role=role,
)

step_process = ProcessingStep(
    name="PreprocessData",
    processor=sklearn_processor,
    outputs=[
        ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
        ProcessingOutput(
            output_name="validation", source="/opt/ml/processing/validation",
        ),
        ProcessingOutput(output_name="test", source="/opt/ml/processing/test"),
    ],
    code=os.path.join(BASE_DIR, "preprocess.py"),
    job_arguments=["--input-data", input_data],
)


# 4. アノテーション(型)定義をしていない
def example_function(x, y):
    # 5. 関数の説明がない
    random_value = random.randint(1, 10)
    sum_of_list = sum(my_list)
    result = x + y + sum_of_list + math.sqrt(random_value)
    return result
