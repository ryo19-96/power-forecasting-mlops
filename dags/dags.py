import datetime
import logging

import boto3
import pytz
from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.providers.amazon.aws.operators.emr import EmrServerlessStartJobOperator
from airflow.utils.dates import days_ago
from check_unprocessed_dates import check_unprocessed_dates, decide_to_run_emr

logger = logging.getLogger(__name__)

table = boto3.resource("dynamodb").Table("watermark-dev")

jst = pytz.timezone("Asia/Tokyo")


def choose_dates(**context) -> str:
    """
    check_unprocessed_dates タスクのXcomから値を取得し、未処理の日付を返す
    次タスクのシェルで渡すため"YYYY-MM-DD, YYYY-MM-DD, ..."の文字列形式で返す

    Args:
        context (dict): Airflowのコンテキスト情報を含む辞書

    Returns:
        (str): 前のタスクから取得した日付("YYYY-MM-DD, YYYY-MM-DD, ...")
    """
    ti = context["ti"]
    target_dates = ti.xcom_pull(task_ids="check_unprocessed_dates_op", key="targets")
    target_dates = ",".join(target_dates)
    logger.info(f"Selected date range for ETL: {target_dates}")

    return target_dates


def get_param(name: str) -> str:
    """
    SSMパラメータストアから指定されたパラメータの値を取得する

    Args:
        name (str): 取得するパラメータの名前

    Returns:
        (str): パラメータの値
    """
    ssm_client = boto3.client("ssm", region_name="ap-northeast-1")
    response = ssm_client.get_parameter(Name=name)
    return response["Parameter"]["Value"]


def update_watermark(date_str: str, job: str = "etl_data") -> None:
    table.update_item(
        Key={"job_name": job},
        UpdateExpression="SET last_processed = :d, updated_at = :t",
        ConditionExpression="attribute_not_exists(last_processed) OR last_processed < :d",
        ExpressionAttributeValues={
            ":d": date_str,
            ":t": datetime.datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


# DAG定義
with DAG(
    dag_id="etl_data",
    start_date=days_ago(1),
    schedule_interval=None,  # Noneに設定すると手動実行のみ
    catchup=False,
    tags=["example"],
) as dag:
    # 未処理の日付をチェックし、XComに格納するタスク
    check_unprocessed_dates_op = PythonOperator(
        task_id="check_unprocessed_dates_op",
        python_callable=check_unprocessed_dates,
        do_xcom_push=True,
    )
    # Xcomに保存されている未処理の日付を取得し、次のタスクで使用するための文字列形式に変換するタスク
    pick_date_range = PythonOperator(
        task_id="pick_date_range",
        python_callable=choose_dates,
        provide_context=True,
        do_xcom_push=True,
    )

    # 前タスクでXcomに保存されているか確認し、EMRジョブを実行するかスキップするかを決定タスク
    branch_to_emr_or_skip = BranchPythonOperator(
        task_id="branch_to_emr_or_skip",
        python_callable=decide_to_run_emr,
        provide_context=True,
    )

    # EMRジョブを実行するタスク
    application_id = get_param("/power-forecasting/dev/emr/app_id")
    execution_role_arn = get_param("/power-forecasting/dev/emr/execution_role_arn")

    run_emr_job = EmrServerlessStartJobOperator(
        task_id="run_emr_job",
        application_id=application_id,
        execution_role_arn=execution_role_arn,
        job_driver={
            "sparkSubmit": {
                "entryPoint": "s3://power-forecasting-emr-scripts-dev/etl_data.py",
                "entryPointArguments": ["--dates", "{{ ti.xcom_pull(task_ids='pick_date_range') }}"],
                "sparkSubmitParameters": (
                    "--conf spark.executor.memory=2g "
                    "--conf spark.executor.cores=1 "
                    "--conf spark.executor.instances=1 "
                    "--conf spark.dynamicAllocation.enabled=false "
                    "--conf spark.driver.memory=1g "
                    "--conf spark.driver.cores=1 "
                ),
            },
        },
        configuration_overrides={
            "monitoringConfiguration": {
                "s3MonitoringConfiguration": {"logUri": "s3://power-forecasting-emr-scripts-dev/logs/"},
            },
        },
    )

    skip_etl = DummyOperator(task_id="skip_etl")

    # EMRジョブ完了後にウォーターマークを更新するタスク
    update_watermark_op = PythonOperator(
        task_id="update_watermark_op",
        python_callable=update_watermark,
        op_kwargs={
            "date_str": "{{ ti.xcom_pull(task_ids='pick_date_range').split(',')[-1].strip() }}",
            "job": "etl_data",
        },
        trigger_rule="all_success",
    )

    check_unprocessed_dates_op >> pick_date_range >> branch_to_emr_or_skip
    branch_to_emr_or_skip >> run_emr_job >> update_watermark_op
    branch_to_emr_or_skip >> skip_etl
