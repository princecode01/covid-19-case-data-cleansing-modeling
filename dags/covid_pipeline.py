from airflow.sdk import dag, task
from pendulum import datetime
import sys

if "/opt/airflow/scripts" not in sys.path:
    sys.path.append("/opt/airflow/scripts")

from bronze import ingest_one_day
from silver import bronze_to_silver
from gold   import silver_to_gold


@dag(
    dag_id="covid_daily_bronze",
    start_date=datetime(2020, 1, 22, tz="UTC"),
    end_date=datetime(2023, 3, 9, tz="UTC"),
    schedule="@daily",
    catchup=True,
    max_active_runs=3,
    tags=["covid", "bronze", "silver", "gold"],
)
def covid_pipeline():

    @task
    def bronze_task(logical_date=None):
        ingest_one_day(logical_date.date())

    @task
    def silver_task():
        bronze_to_silver()

    @task
    def gold_task():
        silver_to_gold()

    bronze = bronze_task()
    silver = silver_task()
    gold   = gold_task()

    bronze >> silver >> gold


covid_pipeline()