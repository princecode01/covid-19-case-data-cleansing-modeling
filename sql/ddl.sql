CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;



CREATE TABLE IF NOT EXISTS bronze.raw_daily_reports (
    -- Metadata columns
    _source_file TEXT,
    _ingested_at TIMESTAMP DEFAULT NOW(),

    -- schema v1 + v2 column names (Jan–Mar 21 2020)
    province_state_v1 TEXT,         -- "Province/State" (slash version)
    country_region_v1 TEXT,         -- "Country/Region"
    last_update_v1    TEXT,
    latitude_v2       TEXT,
    longitude_v2      TEXT,

    -- schema v3 + v4 column names (Mar 22 2020 onwards)
    fips              TEXT,
    admin2            TEXT,
    province_state    TEXT,         -- "Province_State" (underscore version)
    country_region    TEXT,         -- "Country_Region"
    last_update       TEXT,
    lat               TEXT,
    long_             TEXT,
    active            TEXT,
    combined_key      TEXT,
    incident_rate     TEXT,         -- added May 29 2020
    case_fatality_ratio TEXT,       -- added May 29 2020

    -- present in ALL versions
    confirmed         TEXT,
    deaths            TEXT,
    recovered         TEXT
);


CREATE TABLE IF NOT EXISTS silver.covid_cases (
    id               BIGSERIAL PRIMARY KEY,
    report_date      DATE        NOT NULL,
    country   TEXT        NOT NULL,
    province  TEXT,
    confirmed        INTEGER     NOT NULL DEFAULT 0,
    deaths           INTEGER     NOT NULL DEFAULT 0,
    recovered        INTEGER     NOT NULL DEFAULT 0,
    source_file      TEXT,
    UNIQUE (report_date, country, province)
);