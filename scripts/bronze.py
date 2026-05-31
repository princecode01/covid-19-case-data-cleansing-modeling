# -------------------------------------------------
# Version 1: simple download and save to local files
# -------------------------------------------------

# import requests
# import pandas as pd
# from datetime import date, timedelta
# from io import StringIO
# import os

# # ─────────────────────────────────────────────────────────
# # BASE URL
# # Raw GitHub URL to Johns Hopkins daily reports.
# # Only the filename (date) changes per request.
# # ─────────────────────────────────────────────────────────
# BASE_URL = (
#     "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/"
#     "master/csse_covid_19_data/csse_covid_19_daily_reports/"
# )


# def download_csv(target_date: date) -> pd.DataFrame:
#     """
#     Bronze layer — download and land data EXACTLY as received.

#     Rules:
#     - No renaming columns
#     - No dropping columns
#     - No filling nulls
#     - No transforming values
#     - Only _metadata columns are added (prefixed with _)
#     """
#     # Johns Hopkins filenames use MM-DD-YYYY format
#     filename = target_date.strftime("%m-%d-%Y") + ".csv"
#     url = BASE_URL + filename

#     resp = requests.get(url)

#     if resp.status_code != 200:
#         print(f"  ⚠️  Skipping {filename} — not found (status {resp.status_code})")
#         return None

#     # Read EXACTLY as received — no touching
#     df = pd.read_csv(StringIO(resp.text))

#     # ── Only metadata additions are acceptable in Bronze ──
#     # _prefix signals: "we added this, it was not in the source"
#     df["_report_date"] = target_date          # which day this file belongs to
#     df["_source_file"]  = filename             # which file it came from
#     df["_ingested_at"]  = pd.Timestamp.now()   # when we downloaded it

#     return df


# if __name__ == "__main__":
#     # Start from the real first day.
#     # Safe because we are NOT concatting — each file is saved individually.
#     # Silver will handle the schema differences between early and late files.
#     start = date(2020, 1, 22)   # first day Johns Hopkins published data
#     end   = date(2023, 3, 10)   # last day before they shut the repo down

#     # Create output folder
#     os.makedirs("data/raw", exist_ok=True)

#     d          = start
#     total_days = (end - start).days + 1
#     saved      = 0

#     print(f"📥 Downloading {total_days} days ({start} → {end})...\n")

#     while d <= end:
#         df = download_csv(d)
#         if df is not None:
#             # Save each day as its own individual file — NO concat in Bronze
#             # This preserves each file's original schema exactly as Johns Hopkins sent it
#             out_path = f"data/raw/{d.strftime('%m-%d-%Y')}.csv"
#             df.to_csv(out_path, index=False)
#             print(f"  💾 {d.strftime('%m-%d-%Y')}.csv — {len(df)} rows, {len(df.columns)} cols")
#             saved += 1
#         d += timedelta(days=1)

#     print(f"\n✅ Saved {saved} files to data/raw/")
#     print(f"📁 Early files:  6 cols  (old schema)")
#     print(f"📁 Later files: 14 cols  (new schema)")
#     print(f"   → Silver will normalize these differences")


# -------------------------------------------------
# Version 2: direct load to Postgres (no local files)
# -------------------------------------------------

# import requests
# import pandas as pd
# from io import StringIO
# from datetime import date, timedelta
# from sqlalchemy import create_engine, text

# BASE_URL = (
#     "https://raw.githubusercontent.com/CSSEGISandData/COVID-19"
#     "/master/csse_covid_19_data/csse_covid_19_daily_reports/"
# )
# DB_URL = "postgresql://covid_user:covid_pass@localhost/covid_db"

# # ── column aliases: map every known name to a canonical key ──────────
# Columns_Map = {
#     # v1/v2 names (slash style)
#     "Province/State": "province_state_v1",
#     "Country/Region": "country_region_v1",
#     "Last Update":    "last_update_v1",
#     "Latitude":       "latitude_v2",
#     "Longitude":      "longitude_v2",
#     # v3/v4 names (underscore style)
#     "Province_State": "province_state",
#     "Country_Region": "country_region",
#     "Last_Update":    "last_update",
#     "Lat":            "lat",
#     "Long_":          "long_",
#     "FIPS":           "fips",
#     "Admin2":         "admin2",
#     "Active":         "active",
#     "Combined_Key":   "combined_key",
#     "Incident_Rate":  "incident_rate",
#     "Incidence_Rate": "incident_rate",   # typo variant in early files
#     "Case_Fatality_Ratio": "case_fatality_ratio",
#     "Case-Fatality_Ratio": "case_fatality_ratio",  # hyphen variant
#     "Confirmed":      "confirmed",
#     "Deaths":         "deaths",
#     "Recovered":      "recovered",
# }


# def fetch_csv(report_date: date) -> pd.DataFrame | None:
#     fname = report_date.strftime("%m-%d-%Y") + ".csv"          # → "01-22-2020.csv"
#     url   = BASE_URL + fname
#     resp  = requests.get(url)
#     if resp.status_code != 200:
#         print(f"  ⚠️  Skipping {fname} — not found (status {resp.status_code})")
#         return None
#     df = pd.read_csv(StringIO(resp.text), dtype=str)    # dtype=str → everything TEXT
#     df.rename(columns=Columns_Map, inplace=True)
#     df["_source_file"]  = fname
#     df["_ingested_at"] = pd.Timestamp.now()
#     return df

# def load_all():
#     engine = create_engine(DB_URL)
#     start  = date(2020, 1, 22)   # first JHU file
#     end    = date(2023, 3, 9)    # last JHU file

#     # wipe bronze table before a full reload
#     with engine.connect() as conn:
#         conn.execute(text("TRUNCATE TABLE bronze.raw_daily_reports"))
#         conn.commit()


#     d          = start
#     total_rows = 0
#     while d <= end:
#         df = fetch_csv(d)
#         if df is not None:          
#             df.to_sql(
#                 "raw_daily_reports", engine,
#                 schema="bronze", if_exists="append", index=False,
#                 method="multi"         # batch insert, faster
#             )
#             total_rows += len(df)
#             print(f"  ✓ {d} — {len(df)} rows")
#         d += timedelta(days=1)

#     print(f"\n✅ Bronze complete: {total_rows:,} total rows")

# if __name__ == "__main__":
#     load_all()

# -------------------------------------------------
# Version 3: direct load to Postgres with resume capability
# -------------------------------------------------

# import requests
# import pandas as pd
# from io import StringIO
# from datetime import date, timedelta
# from sqlalchemy import create_engine, text
# from sqlalchemy.exc import SQLAlchemyError
# from pandas.errors import ParserError


# BASE_URL = (
#     "https://raw.githubusercontent.com/CSSEGISandData/COVID-19"
#     "/master/csse_covid_19_data/csse_covid_19_daily_reports/"
# )

# DB_URL = "postgresql://covid_user:covid_pass@localhost/covid_db"


# # ── column aliases ─────────────────────────────────────────────────────

# Columns_Map = {
#     "Province/State": "province_state_v1",
#     "Country/Region": "country_region_v1",
#     "Last Update": "last_update_v1",
#     "Latitude": "latitude_v2",
#     "Longitude": "longitude_v2",

#     "Province_State": "province_state",
#     "Country_Region": "country_region",
#     "Last_Update": "last_update",
#     "Lat": "lat",
#     "Long_": "long_",
#     "FIPS": "fips",
#     "Admin2": "admin2",
#     "Active": "active",
#     "Combined_Key": "combined_key",
#     "Incident_Rate": "incident_rate",
#     "Incidence_Rate": "incident_rate",
#     "Case_Fatality_Ratio": "case_fatality_ratio",
#     "Case-Fatality_Ratio": "case_fatality_ratio",
#     "Confirmed": "confirmed",
#     "Deaths": "deaths",
#     "Recovered": "recovered",
# }


# # ── fetch one csv ──────────────────────────────────────────────────────

# def fetch_csv(report_date: date) -> pd.DataFrame | None:

#     fname = report_date.strftime("%m-%d-%Y") + ".csv"
#     url = BASE_URL + fname

#     try:
#         resp = requests.get(url)

#         if resp.status_code != 200:
#             print(f"⚠️ File not found: {fname}")
#             return None

#         # safer parsing
#         df = pd.read_csv(StringIO(resp.text), dtype=str)
 
#         if df.empty:
#             print(f"⚠️ Empty file: {fname}")
#             return None

#         df.rename(columns=Columns_Map, inplace=True)

#         # add metadata
#         df["_source_file"] = fname
#         df["_ingested_at"] = pd.Timestamp.now()

#         return df

#     except ParserError as e:
#         print(f"❌ Parser error in {fname}: {e}")
#         return None

#     except Exception as e:
#         print(f"❌ Unexpected error in {fname}: {e}")
#         return None


# # ── get last ingested file ─────────────────────────────────────────────

# def get_resume_date(engine):

#     query = """
#         SELECT MAX(_source_file)
#         FROM bronze.raw_daily_reports
#     """

#     with engine.connect() as conn:
#         result = conn.execute(text(query)).scalar()

#     if not result:
#         return date(2020, 1, 22)

#     # convert filename back to date
#     last_date = pd.to_datetime(
#         result.replace(".csv", ""),
#         format="%m-%d-%Y"
#     ).date()

#     # continue AFTER last ingested date
#     return last_date + timedelta(days=1)


# # ── main loader ────────────────────────────────────────────────────────

# def load_all():

#     engine = create_engine(DB_URL)

#     start = get_resume_date(engine)
#     end = date(2023, 3, 9)

#     print(f"\n🚀 Starting ingestion from: {start}\n")

#     d = start
#     total_rows = 0

#     while d <= end:
#         try:

#             df = fetch_csv(d)

#             if df is not None:

#                 df.to_sql(
#                     "raw_daily_reports",
#                     engine,
#                     schema="bronze",
#                     if_exists="append",
#                     index=False,
#                     method="multi",
#                     chunksize=1000
#                 )

#                 total_rows += len(df)

#                 print(f"✓ {d} — {len(df)} rows inserted")

#             else:
#                 print(f"⚠️ Skipped {d}")

#         except SQLAlchemyError as e:
#             print(f"❌ Database error on {d}: {e}")

#         except Exception as e:
#             print(f"❌ Unknown error on {d}: {e}")

#         # IMPORTANT:
#         # always increment date
#         d += timedelta(days=1)

#     print(f"\n✅ Ingestion complete")
#     print(f"✅ Total inserted rows: {total_rows:,}")


# if __name__ == "__main__":
#     load_all()





# -----------------------------------------------------------------------
# Version 4: adding ingest_one_day function for Airflow daily scheduling
# -----------------------------------------------------------------------

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

DB_URL = "postgresql://covid_user:covid_pass@localhost/covid_db"

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