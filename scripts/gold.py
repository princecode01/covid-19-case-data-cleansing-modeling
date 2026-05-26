from sqlalchemy import create_engine, text

DB_URL = "postgresql://covid_user:covid_pass@localhost/covid_db"

DIM_DATE_SQL = """
INSERT INTO gold.dim_date (full_date, year, month, day, quarter, month_name, week_number, day_of_week)
SELECT DISTINCT
    report_date,
    EXTRACT(YEAR  FROM report_date)::SMALLINT,
    EXTRACT(MONTH FROM report_date)::SMALLINT,
    EXTRACT(DAY   FROM report_date)::SMALLINT,
    EXTRACT(QUARTER   FROM report_date)::SMALLINT,
    TO_CHAR(report_date, 'Month'),
    EXTRACT(WEEK FROM report_date),
    TO_CHAR(report_date, 'Day')
FROM silver.covid_cases
ON CONFLICT (full_date) DO NOTHING;
"""

DIM_LOCATION_SQL = """
INSERT INTO gold.dim_location (country, province, lat, long_)
SELECT DISTINCT
    country,
    province,
    AVG(lat)   OVER (PARTITION BY country, province),
    AVG(long_) OVER (PARTITION BY country, province)
FROM silver.covid_cases
ON CONFLICT (country, province) DO NOTHING;
"""

FACT_SQL = """
INSERT INTO gold.fact_covid_cases
    (date_id, location_id, confirmed, deaths, recovered,
     new_confirmed, new_deaths)

WITH windowed AS (
    SELECT
        s.report_date,
        s.country,
        s.province,
        s.confirmed,
        s.deaths,
        s.recovered,
        -- daily new cases = today minus yesterday for this location
        s.confirmed - LAG(s.confirmed) OVER (
            PARTITION BY s.country, s.province
            ORDER BY s.report_date
        ) AS new_confirmed,
        s.deaths - LAG(s.deaths) OVER (
            PARTITION BY s.country, s.province
            ORDER BY s.report_date
        ) AS new_deaths
    FROM silver.covid_cases s
)
SELECT
    d.date_id,
    l.location_id,
    w.confirmed,
    w.deaths,
    w.recovered,
    GREATEST(w.new_confirmed, 0),           -- clip negatives (corrections)
    GREATEST(w.new_deaths, 0)
FROM windowed w
JOIN gold.dim_date     d ON d.full_date = w.report_date
JOIN gold.dim_location l ON l.country   = w.country
                        AND l.province IS NOT DISTINCT FROM w.province
ON CONFLICT (date_id, location_id) DO UPDATE SET
    confirmed     = EXCLUDED.confirmed,
    deaths        = EXCLUDED.deaths,
    recovered     = EXCLUDED.recovered,
    new_confirmed = EXCLUDED.new_confirmed,
    new_deaths    = EXCLUDED.new_deaths
"""

def silver_to_gold():
    engine = create_engine(DB_URL)
    truncate_sql = """
            TRUNCATE TABLE gold.fact_covid_cases, gold.dim_date, gold.dim_location
            RESTART IDENTITY CASCADE;
"""
    with engine.connect() as conn:
        # Start a transaction block
        with conn.begin():
            # Truncate all tables
            print("Truncating Gold schema tables")
            conn.execute(text(truncate_sql))

            # Tables insertion
            print("Populating dim_date...")
            conn.execute(text(DIM_DATE_SQL))

            print("Populating dim_location...")
            conn.execute(text(DIM_LOCATION_SQL))
            
            print("Populating fact_covid_cases...")
            conn.execute(text(FACT_SQL))

    print("✅ Gold complete")

if __name__ == "__main__":
    silver_to_gold()