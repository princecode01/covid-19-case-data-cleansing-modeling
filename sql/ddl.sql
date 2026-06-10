CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;


-- ── Bronze ────────────────────────────────────────────────────────
DROP TABLE IF EXISTS bronze.raw_daily_reports;

CREATE TABLE bronze.raw_daily_reports (
    -- Metadata columns
    _source_file        TEXT,         
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),  -- audit: when we downloaded it

    -- v1 / v2 column names (Jan 22 – Mar 21 2020) — slash style
    province_state_v1   TEXT,         -- original: "Province/State"
    country_region_v1   TEXT,         -- original: "Country/Region"
    last_update_v1      TEXT,         -- original: "Last Update"
    latitude_v1         TEXT,         -- added Mar 1: "Latitude"
    longitude_v1        TEXT,         -- added Mar 1: "Longitude"

    -- v3 / v4 column names (Mar 22 2020 onwards) — underscore style
    fips                TEXT,         -- US county code
    admin2              TEXT,         -- US county name
    province_state      TEXT,         -- renamed from "Province/State"
    country_region      TEXT,         -- renamed from "Country/Region"
    last_update         TEXT,         -- renamed from "Last Update"
    lat                 TEXT,
    long_               TEXT,
    active              TEXT,
    combined_key        TEXT,
    incident_rate       TEXT,         
    case_fatality_ratio TEXT,         

    -- present in ALL schema versions
    confirmed           TEXT,
    deaths              TEXT,
    recovered           TEXT
);

-- ── Silver ────────────────────────────────────────────────────────
DROP TABLE IF EXISTS silver.covid_cases;

CREATE TABLE silver.covid_cases (
    id               BIGSERIAL PRIMARY KEY,
    report_date      DATE        NOT NULL,
    country_region   TEXT        NOT NULL,
    province_state   TEXT,                   -- NULL for country-level rows
    admin2           TEXT,                   -- US county, NULL elsewhere
    confirmed        INTEGER     NOT NULL DEFAULT 0,
    deaths           INTEGER     NOT NULL DEFAULT 0,
    recovered        INTEGER     NOT NULL DEFAULT 0,
    lat              NUMERIC(9,6),
    long_            NUMERIC(9,6),
    source_file      TEXT,                   
    UNIQUE (report_date, country_region, province_state, admin2)
);

-- ── Gold ────────────────────────────────────────────────────────
-- Drop fact FIRST — it references dim_date and dim_location
-- If you drop dim_date first, Postgres refuses because fact still points to it
DROP TABLE IF EXISTS gold.fact_covid_cases;
DROP TABLE IF EXISTS gold.dim_date;
DROP TABLE IF EXISTS gold.dim_location;


CREATE TABLE gold.dim_date (
    date_id      SERIAL PRIMARY KEY,
    full_date    DATE   UNIQUE NOT NULL,
    year         SMALLINT,
    month        SMALLINT,
    day          SMALLINT,
    quarter      SMALLINT,
    month_name   TEXT,
    week_number  SMALLINT,
    day_of_week  TEXT
);

CREATE TABLE gold.dim_location (
    location_id    SERIAL PRIMARY KEY,
    country_region        TEXT NOT NULL,
    province_state       TEXT,
    admin2         TEXT,            -- US county, NULL elsewhere
    lat            NUMERIC(9,6),
    long_          NUMERIC(9,6),
    UNIQUE (country_region, province_state, admin2)
);

CREATE TABLE gold.fact_covid_cases (
    cases_id        BIGSERIAL PRIMARY KEY,
    date_id        INTEGER NOT NULL REFERENCES gold.dim_date(date_id),
    location_id    INTEGER NOT NULL REFERENCES gold.dim_location(location_id),
    confirmed      INTEGER NOT NULL DEFAULT 0,
    deaths         INTEGER NOT NULL DEFAULT 0,
    recovered      INTEGER NOT NULL DEFAULT 0,
    new_confirmed  INTEGER,
    new_deaths     INTEGER,
    moving_avg_7d  NUMERIC(12,2), -- 7-day rolling avg of new_confirmed
    UNIQUE (date_id, location_id)
);


CREATE OR REPLACE VIEW gold.v_global_daily_cases AS
SELECT
    d.full_date,
    SUM(f.new_confirmed) AS new_cases
FROM gold.fact_covid_cases f
JOIN gold.dim_date d
    ON f.date_id = d.date_id
GROUP BY d.full_date
ORDER BY d.full_date;


CREATE OR REPLACE VIEW gold.v_global_cumulative_metrics AS
SELECT
    d.full_date,
    SUM(f.confirmed) AS cumulative_cases,
    SUM(f.deaths) AS cumulative_deaths,
    SUM(f.recovered) AS cumulative_recoveries
FROM gold.fact_covid_cases f
JOIN gold.dim_date d
    ON f.date_id = d.date_id
GROUP BY d.full_date
ORDER BY d.full_date;


CREATE OR REPLACE VIEW gold.v_moving_avg_7d AS
SELECT 
    d.full_date,
    f.new_confirmed,
    f.moving_avg_7d
FROM gold.fact_covid_cases f
JOIN gold.dim_date d
    ON f.date_id = d.date_id


