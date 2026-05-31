CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;



CREATE TABLE IF NOT EXISTS bronze.raw_daily_reports (

    -- metadata: added by us, not in the CSV (_prefix = "we added this")
    _source_file        TEXT,         -- e.g. "01-22-2020.csv" (traceability)
    _ingested_at        TIMESTAMP DEFAULT NOW(),  -- audit: when we downloaded it

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
    incident_rate       TEXT,         -- added May 29 2020
    case_fatality_ratio TEXT,         -- added May 29 2020

    -- present in ALL schema versions
    confirmed           TEXT,
    deaths              TEXT,
    recovered           TEXT
);


CREATE TABLE IF NOT EXISTS silver.covid_cases (
    id               BIGSERIAL PRIMARY KEY,
    report_date      DATE        NOT NULL,
    country          TEXT        NOT NULL,
    province         TEXT,
    lat              NUMERIC(9,6),
    long_            NUMERIC(9,6),
    confirmed        INTEGER     NOT NULL DEFAULT 0,
    deaths           INTEGER     NOT NULL DEFAULT 0,
    recovered        INTEGER     NOT NULL DEFAULT 0,
    source_file      TEXT,
    UNIQUE (report_date, country, province)
);


CREATE TABLE IF NOT EXISTS gold.dim_date (
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

CREATE TABLE IF NOT EXISTS gold.dim_location (
    location_id    SERIAL PRIMARY KEY,
    country TEXT NOT NULL,
    province TEXT,
    lat       NUMERIC(9,6),
    long_     NUMERIC(9,6),
    UNIQUE (country, province)
);

CREATE TABLE IF NOT EXISTS gold.fact_covid_cases (
    cases_id        BIGSERIAL PRIMARY KEY,
    date_id        INTEGER NOT NULL REFERENCES gold.dim_date(date_id),
    location_id    INTEGER NOT NULL REFERENCES gold.dim_location(location_id),
    confirmed      INTEGER NOT NULL DEFAULT 0,
    deaths         INTEGER NOT NULL DEFAULT 0,
    recovered      INTEGER NOT NULL DEFAULT 0,
    new_confirmed  INTEGER,
    new_deaths     INTEGER,
    UNIQUE (date_id, location_id)
);