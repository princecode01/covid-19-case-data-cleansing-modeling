import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = "postgresql://covid_user:covid_pass@localhost/covid_db"

# ── Country name normalization lookup ────────────────────────────────
COUNTRY_MAP = {
    "Bahamas, The":                      "Bahamas",
    "Burma":                             "Myanmar",
    "Cabo Verde":                        "Cape Verde",
    "Czech Republic":                    "Czechia",
    "East Timor":                        "Timor-Leste",
    "Gambia, The":                       "Gambia",
    "Hong Kong SAR":                     "Hong Kong",
    "Iran (Islamic Republic of)":        "Iran",
    "Ivory Coast":                       "Cote d'Ivoire",
    "Korea, North":                      "North Korea",
    "Korea, South":                      "South Korea",
    "Macao SAR":                         "Macau",
    "Mainland China":                    "China",
    "occupied Palestinian territory":    "Palestine",
    "Republic of Ireland":               "Ireland",
    "Republic of Korea":                 "South Korea",
    "Republic of Moldova":               "Moldova",
    "Republic of the Congo":             "Congo (Brazzaville)",
    "Reunion":                           "Réunion",
    "Russian Federation":                "Russia",
    "Saint Barthelemy":                  "Saint Barthélemy",
    "St. Martin":                        "Saint Martin",
    "Taipei and environs":               "Taiwan",
    "Taiwan*":                           "Taiwan",
    "The Bahamas":                       "Bahamas",
    "The Gambia":                        "Gambia",
    "US":                                "United States",
    "Vatican City":                      "Holy See",
    "Viet Nam":                          "Vietnam",
    "West Bank and Gaza":                "Palestine",
}

NON_COUNTRY = {
    "Cruise Ship",
    "Diamond Princess",
    "MS Zaandam",
    "Summer Olympics 2020",
    "Winter Olympics 2022",
    "Others",
}


def coerce_int(series: pd.Series) -> pd.Series:
    """Convert a TEXT column to int, treating blanks/negatives as 0."""
    return (
        pd.to_numeric(series, errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .astype(int)
    )

def unify_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge the 4-schema mess into a single canonical shape.
    v1/v2 files have province_state_v1, country_region_v1, etc.
    v3/v4 files have province_state, country_region, etc.
    We combine them with coalesce logic.
    """
    df["country_region"] = df.get("country_region", pd.Series()).combine_first(
                              df.get("country_region_v1", pd.Series()))
    df["province_state"] = df.get("province_state", pd.Series()).combine_first(
                              df.get("province_state_v1", pd.Series()))
    return df

def bronze_to_silver():
    engine = create_engine(DB_URL)

    # 1. Read all Bronze data
    print("Reading Bronze...")
    df = pd.read_sql("SELECT * FROM bronze.raw_daily_reports", engine)
    print(f"  {len(df):,} raw rows loaded")

    print("------------------------------")

    print("Cleaning and transforming to Silver...")
    # 2. Unify the 4 schemas into one shape
    df = unify_columns(df)
    print(f"  {len(df):,} rows after unifying columns")

    # 3. Standardize dates
    #    Files have formats like "1/22/2020 17:00", "2020-01-22T17:00:00", "01/22/2020"
    df["report_date"] = (
        pd.to_datetime(
            df["last_update"].combine_first(df["last_update_v1"]),
            errors="coerce"
        ).dt.date
    )
    
    # Fall back: derive date from the source filename if Last Update is null
    mask = df["report_date"].isna()
    df.loc[mask, "report_date"] = pd.to_datetime(
        df.loc[mask, "_source_file"].str.replace(".csv", "", regex=False),
        format="%m-%d-%Y"
    ).dt.date

    # 4. Normalize country names
    df["country_region"] = df["country_region"].str.strip().replace(COUNTRY_MAP)

    # Exclude non-country entities 
    df = df[~df["country_region"].isin(NON_COUNTRY)]


    # 5. Fix numeric columns (negatives = data corrections, treat as 0)
    for col in ["confirmed", "deaths", "recovered", "active"]:
        df[col] = coerce_int(df[col])

    # # 6. Fix lat/long
    # df["lat"]   = pd.to_numeric(df["lat"],   errors="coerce")
    # df["long_"] = pd.to_numeric(df["long_"], errors="coerce")

    # 7. Drop rows missing the essentials
    df = df.dropna(subset=["report_date", "country_region"])
    print(f"  {len(df):,} rows after dropping missing dates/countries")

    # 8. Remove duplicates (same date + country + province )
    df = df.drop_duplicates(
        subset=["report_date", "country_region", "province_state"],
        keep="last"
    )
    print(f"  {len(df):,} rows after deduplication")

    # 9. Select final columns for Silver
    silver = df[[
        "report_date", "country_region", "province_state",
         "confirmed", "deaths", "recovered", "_source_file"
    ]].rename(columns={"_source_file": "source_file", "country_region": "country", "province_state": "province"})

    # 10. Write to Silver (truncate first for idempotency)
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE silver.covid_cases RESTART IDENTITY"))
        conn.commit()

    silver.to_sql(
        "covid_cases", engine,
        schema="silver", if_exists="append",
        index=False, method="multi"
    )
    print(f"✅ Silver complete: {len(silver):,} clean rows")

if __name__ == "__main__":
    bronze_to_silver()