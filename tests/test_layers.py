import os
import pandas as pd
from sqlalchemy import create_engine

DB_HOST = os.getenv("DB_HOST", "localhost")  # default to localhost
DB_URL = f"postgresql://covid_user:covid_pass@{DB_HOST}/covid_db"

engine = create_engine(DB_URL)

def q(sql): return pd.read_sql(sql, engine)

# ── Bronze tests ──────────────────────────────────────────────────────
def test_bronze_has_rows():
    # Full dataset: 1,143 files × avg ~200 rows = ~1M+ rows expected
    cnt = q("SELECT COUNT(*) AS n FROM bronze.raw_daily_reports")["n"][0]
    assert cnt > 1_000_000, "Bronze should have over 1M rows"

def test_bronze_metadata_columns_present():
    # Every Bronze row must have our metadata columns
    nulls = q("SELECT COUNT(*) AS n FROM bronze.raw_daily_reports WHERE _source_file IS NULL")["n"][0]
    assert nulls == 0, "Every Bronze row must have _source_file"

def test_bronze_all_text_columns():
    # Spot-check: confirmed should be stored as TEXT in Bronze (no type casting)
    result = q("""
        SELECT data_type FROM information_schema.columns
        WHERE table_schema='bronze' AND table_name='raw_daily_reports'
        AND column_name='confirmed'
    """)
    assert result["data_type"][0] == "text", "Bronze confirmed must be TEXT"


# ── Silver tests ──────────────────────────────────────────────────────
def test_silver_no_negative_cases():
    bad = q("SELECT COUNT(*) AS n FROM silver.covid_cases WHERE confirmed < 0 OR deaths < 0")["n"][0]
    assert bad == 0, f"Found {bad} rows with negative confirmed or deaths counts in Silver"

def test_silver_no_null_dates():
    bad = q("SELECT COUNT(*) AS n FROM silver.covid_cases WHERE report_date IS NULL")["n"][0]
    assert bad == 0, "Every Silver row must have a valid date"

def test_silver_country_names_unified():
    # "US" must not exist — only "United States"
    bad = q("SELECT COUNT(*) AS n FROM silver.covid_cases WHERE country_region = 'US'")["n"][0]
    assert bad == 0, "'US' should be normalized to 'United States'"

def test_silver_date_range():
    result = q("SELECT MIN(report_date) AS mn, MAX(report_date) AS mx FROM silver.covid_cases")
    assert str(result["mn"][0]) == "2020-01-22", "First date should be 2020-01-22"
    assert str(result["mx"][0]) == "2023-03-09", "Last date should be 2023-03-09"

def test_silver_no_duplicates():
    bad = q("""
        SELECT COUNT(*) AS n FROM (
            SELECT report_date, country_region, province_state,
                   COUNT(*) AS cnt
            FROM silver.covid_cases
            GROUP BY report_date, country_region, province_state
            HAVING COUNT(*) > 1
        ) t
    """)["n"][0]
    assert bad == 0, "Silver must have no duplicate date+location rows"


# ── Gold tests ────────────────────────────────────────────────────────
def test_gold_no_orphan_facts():
    # Every fact row must link to a valid dim_date
    bad = q("""
        SELECT COUNT(*) AS n FROM gold.fact_covid_cases f
        LEFT JOIN gold.dim_date d ON f.date_id = d.date_id
        WHERE d.date_id IS NULL
    """)["n"][0]
    assert bad == 0, "Every fact must link to a valid dim_date"

def test_gold_moving_avg_not_null_after_day7():
    # After 7 days from start, moving_avg_7d must be populated
    bad = q("""
        SELECT COUNT(*) AS n FROM gold.fact_covid_cases f
        JOIN gold.dim_date d ON f.date_id = d.date_id
        WHERE d.full_date > '2020-01-29'
        AND f.moving_avg_7d IS NULL
    """)["n"][0]
    assert bad == 0, "moving_avg_7d should be populated after day 7"

def test_gold_no_negative_new_cases():
    # GREATEST(..., 0) in the Gold SQL should have clipped all negatives
    bad = q("SELECT COUNT(*) AS n FROM gold.fact_covid_cases WHERE new_confirmed < 0")["n"][0]
    assert bad == 0, "No negative new_confirmed values in Gold"