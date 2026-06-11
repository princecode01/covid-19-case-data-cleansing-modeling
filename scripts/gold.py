import os
from sqlalchemy import create_engine, text
from datetime import date

DB_HOST = os.getenv("DB_HOST", "localhost")  # default to localhost
DB_URL = f"postgresql://covid_user:covid_pass@{DB_HOST}/covid_db"


GET_NEW_DATES_SQL = """
    SELECT DISTINCT report_date FROM silver.covid_cases
    EXCEPT
    SELECT DISTINCT full_date   FROM gold.dim_date
    ORDER BY 1
"""

# ── dim_date — insert only new dates ─────────────────────────────
DIM_DATE_SQL = """
INSERT INTO gold.dim_date
    (full_date, year, month, day, quarter, month_name, week_number, day_of_week)
SELECT DISTINCT
    report_date,
    EXTRACT(YEAR    FROM report_date)::SMALLINT,
    EXTRACT(MONTH   FROM report_date)::SMALLINT,
    EXTRACT(DAY     FROM report_date)::SMALLINT,
    EXTRACT(QUARTER FROM report_date)::SMALLINT,
    TO_CHAR(report_date, 'Month'),
    EXTRACT(WEEK    FROM report_date)::SMALLINT,
    TO_CHAR(report_date, 'Day')
FROM silver.covid_cases
WHERE report_date = ANY(:new_dates)
ON CONFLICT (full_date) DO NOTHING;
"""


# ── dim_location — insert only locations that appear in the new dates ─────
DIM_LOCATION_SQL = """
INSERT INTO gold.dim_location
    (country_region, province_state, lat, long_)
SELECT DISTINCT ON (country_region, province_state)
    country_region,
    province_state,
    AVG(lat)   OVER (PARTITION BY country_region, province_state),
    AVG(long_) OVER (PARTITION BY country_region, province_state)
FROM silver.covid_cases
WHERE report_date = ANY(:new_dates)
ON CONFLICT (country_region, province_state) DO NOTHING;
"""

# ── fact — insert only today's rows, but read 7-day history ───────
FACT_SQL = """
INSERT INTO gold.fact_covid_cases
    (date_id, location_id, confirmed, deaths, recovered, active,
     new_confirmed, new_deaths, moving_avg_7d)

WITH history AS (
    -- Read today + 6 days before it per location
    -- This gives LAG() and the 7-day window enough history to work correctly
    SELECT
        s.report_date,
        s.country_region,
        s.province_state,
        s.confirmed,
        s.deaths,
        s.recovered,
        s.active
    FROM silver.covid_cases s
    WHERE s.report_date >= (
        -- go back 7 days from the earliest new date
        -- so the window function has enough rows to compute correctly
        SELECT MIN(d) - INTERVAL '7 days'
        FROM UNNEST(CAST(:new_dates AS date[])) AS d
    )
),
windowed AS (
    SELECT
        h.report_date,
        h.country_region,
        h.province_state,
        h.confirmed,
        h.deaths,
        h.recovered,
        h.active,
        h.confirmed - LAG(h.confirmed) OVER (
            PARTITION BY h.country_region, h.province_state 
            ORDER BY h.report_date
        ) AS new_confirmed_raw,
        h.deaths - LAG(h.deaths) OVER (
            PARTITION BY h.country_region, h.province_state 
            ORDER BY h.report_date
        ) AS new_deaths_raw
    FROM history h
)
SELECT DISTINCT ON (d.date_id, l.location_id)
    d.date_id,
    l.location_id,
    w.confirmed,
    w.deaths,
    w.recovered,
    w.active,
    GREATEST(w.new_confirmed_raw, 0) AS new_confirmed,
    GREATEST(w.new_deaths_raw,    0) AS new_deaths,
    AVG(GREATEST(w.new_confirmed_raw, 0)) OVER (
        PARTITION BY w.country_region, w.province_state
        ORDER BY w.report_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS moving_avg_7d
FROM windowed w
JOIN gold.dim_date d
    ON  d.full_date = w.report_date
JOIN gold.dim_location l
    ON  l.country_region   = w.country_region
    AND l.province_state IS NOT DISTINCT FROM w.province_state
WHERE w.report_date = ANY(:new_dates)   -- only INSERT today's rows
ORDER BY d.date_id, l.location_id 
ON CONFLICT (date_id, location_id) DO UPDATE SET
    confirmed     = EXCLUDED.confirmed,
    deaths        = EXCLUDED.deaths,
    recovered     = EXCLUDED.recovered,
    new_confirmed = EXCLUDED.new_confirmed,
    new_deaths    = EXCLUDED.new_deaths,
    moving_avg_7d = EXCLUDED.moving_avg_7d;
"""


# Get dates that are in Silver but not yet in Gold — these are the dates we need to process.
def get_new_dates(conn) -> list[date]:
    result = conn.execute(text(GET_NEW_DATES_SQL))
    return [row[0] for row in result]




# This is the main function that runs the Gold pipeline. It checks for new dates in Silver, and if it finds any, it runs the SQL queries to populate the dim_date, dim_location, and fact_covid_cases tables in Gold.
def silver_to_gold() -> None:

    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        with conn.begin():

            new_dates = get_new_dates(conn)

            if not new_dates:
                print("🥇 Gold is already up to date — nothing to process")
                return

            print(f"🥇 Loading {len(new_dates)} new date(s) into Gold: {[str(d) for d in new_dates]}\n")

            # Pass new_dates as a parameter to the SQL queries
            params = {"new_dates": new_dates}

            print("  Populating dim_date...")
            conn.execute(text(DIM_DATE_SQL), params)

            print("  Populating dim_location...")
            conn.execute(text(DIM_LOCATION_SQL), params)

            print("  Populating fact_covid_cases...")
            conn.execute(text(FACT_SQL), params)

    print(f"\n✅ Gold complete — {len(new_dates)} new date(s) loaded")


if __name__ == "__main__":
    silver_to_gold()