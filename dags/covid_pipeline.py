from airflow.sdk import dag, task
from pendulum import datetime


def setup_scripts_path():
    import sys
    if "/opt/airflow/scripts" not in sys.path:
        sys.path.append("/opt/airflow/scripts")


@dag(
    dag_id="covid_daily_bronze",
    start_date=datetime(2020, 1, 22, tz="UTC"),
    end_date=datetime(2023, 3, 9, tz="UTC"),
    schedule="@daily",
    catchup=True,
    max_active_runs=1,
    tags=["covid", "bronze", "silver", "gold"],
)
def covid_pipeline():

    @task
    def bronze_task(logical_date=None):
        setup_scripts_path()
        from bronze import ingest_one_day
        ingest_one_day(logical_date.date())

    @task
    def silver_task():
        setup_scripts_path()
        from silver import bronze_to_silver
        bronze_to_silver()

    @task
    def gold_task():
        setup_scripts_path()
        from gold import silver_to_gold
        silver_to_gold()

    bronze = bronze_task()
    silver = silver_task()
    gold   = gold_task()

    bronze >> silver >> gold


covid_pipeline()