from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, date
import sys

sys.path.append("/opt/airflow/scripts")

from bronze import ingest_one_day
from silver import bronze_to_silver
from gold   import silver_to_gold


def bronze_task(**context):
    # Airflow 3: logical_date replaces execution_date
    logical_date = context["logical_date"].date()
    ingest_one_day(logical_date)


with DAG(
    dag_id="covid_daily_bronze",
    start_date=datetime(2020, 1, 22),
    schedule="@daily",
    catchup=True,      # True here — tells Airflow to backfill all past dates
    max_active_runs=3, # run 3 dates in parallel to speed up the backfill
    tags=["covid", "bronze"],
) as dag:

    bronze = PythonOperator(
        task_id="ingest_bronze",
        python_callable=bronze_task,
    )

    silver = PythonOperator(
        task_id="clean_silver",
        python_callable=bronze_to_silver,
    )

    gold = PythonOperator(
        task_id="model_gold",
        python_callable=silver_to_gold,
    )

    bronze >> silver >> gold