import os
import requests
import pandas as pd
from io import StringIO
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from pandas.errors import ParserError


BASE_URL = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19"
    "/master/csse_covid_19_data/csse_covid_19_daily_reports/"
)

DB_HOST = os.getenv("DB_HOST", "localhost")  # default to localhost
DB_URL = f"postgresql://covid_user:covid_pass@{DB_HOST}/covid_db"

COLUMNS_MAP = {
    "Province/State":      "province_state_v1",
    "Country/Region":      "country_region_v1",
    "Last Update":         "last_update_v1",
    "Latitude":            "latitude_v1",
    "Longitude":           "longitude_v1",
    "Province_State":      "province_state",
    "Country_Region":      "country_region",
    "Last_Update":         "last_update",
    "Lat":                 "lat",
    "Long_":               "long_",
    "FIPS":                "fips",
    "Admin2":              "admin2",
    "Active":              "active",
    "Combined_Key":        "combined_key",
    "Incident_Rate":       "incident_rate",
    "Incidence_Rate":      "incident_rate",
    "Case_Fatality_Ratio": "case_fatality_ratio",
    "Case-Fatality_Ratio": "case_fatality_ratio",
    "Confirmed":           "confirmed",
    "Deaths":              "deaths",
    "Recovered":           "recovered",
}


def fetch_csv(report_date: date) -> pd.DataFrame | None:
    fname = report_date.strftime("%m-%d-%Y") + ".csv"
    url = BASE_URL + fname

    try:
        resp = requests.get(url)

        if resp.status_code != 200:
            print(f"⚠️ File not found: {fname}")
            return None

        df = pd.read_csv(StringIO(resp.text), dtype=str)

        if df.empty:
            print(f"⚠️ Empty file: {fname}")
            return None

        df.rename(columns=COLUMNS_MAP, inplace=True)
        df["_source_file"] = fname
        df["_ingested_at"] = datetime.now(timezone.utc)

        return df

    except ParserError as e:
        print(f"❌ Parser error in {fname}: {e}")
        return None

    except Exception as e:
        print(f"❌ Unexpected error in {fname}: {e}")
        return None


def ingest_one_day(report_date: date) -> None:
    """
    Downloads and ingests exactly one day's CSV file.
    This is the function Airflow calls — it receives the date
    from the DAG's logical_date context, so it always knows
    exactly which day to process.
    No resume logic needed — Airflow handles retries and reruns.
    """
    engine = create_engine(DB_URL)

    # Check if this date's file has already been ingested — if so, skip to avoid duplicates.
    source_file = report_date.strftime("%m-%d-%Y") + ".csv"
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM bronze.raw_daily_reports WHERE _source_file = :source_file)"),
            {"source_file": source_file}
        )
        if result.scalar():  
            print(f"⏭️  {source_file} already in Bronze — skipping")
            return

    df = fetch_csv(report_date)

    if df is None:
        print(f"⚠️ Nothing to ingest for {report_date}")
        return

    try:
        df.to_sql(
            "raw_daily_reports",
            engine,
            schema="bronze",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )
        print(f"✅ {report_date} — {len(df)} rows inserted")

    except SQLAlchemyError as e:
        print(f"❌ DB error on {report_date}: {e}")
        raise   # re-raise so Airflow marks the task as FAILED and retries


def load_all() -> None:
    """
    One-time historical backfill — run manually once, not via Airflow.
    Uses get_resume_date() to safely continue from where it stopped.
    """
    engine = create_engine(DB_URL)
    start = get_resume_date(engine)
    end = date(2023, 3, 9)

    print(f"\n🚀 Starting backfill from {start} → {end}\n")

    d = start
    total_rows = 0

    while d <= end:
        try:
            df = fetch_csv(d)
            if df is not None:
                df.to_sql(
                    "raw_daily_reports", engine,
                    schema="bronze", if_exists="append",
                    index=False, method="multi", chunksize=1000,
                )
                total_rows += len(df)
                print(f"✓ {d} — {len(df)} rows")
            else:
                print(f"⚠️ Skipped {d}")

        except SQLAlchemyError as e:
            print(f"❌ DB error on {d}: {e}")

        except Exception as e:
            print(f"❌ Unknown error on {d}: {e}")

        d += timedelta(days=1)

    print(f"\n✅ Backfill complete — {total_rows:,} total rows")


def get_resume_date(engine) -> date:
    """
    Only used by load_all() for the one-time historical backfill.
    Not needed for Airflow — Airflow passes the date directly.
    """
    query = "SELECT MAX(_source_file) FROM bronze.raw_daily_reports"
    with engine.connect() as conn:
        result = conn.execute(text(query)).scalar()

    if not result:
        return date(2020, 1, 22)

    last_date = pd.to_datetime(
        result.replace(".csv", ""), format="%m-%d-%Y"
    ).date()

    return last_date + timedelta(days=1)


if __name__ == "__main__":
    load_all()