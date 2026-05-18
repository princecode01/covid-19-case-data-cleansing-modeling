import requests
import pandas as pd
from datetime import date, timedelta
from io import StringIO
import os

# ─────────────────────────────────────────────────────────
# BASE URL
# Raw GitHub URL to Johns Hopkins daily reports.
# Only the filename (date) changes per request.
# ─────────────────────────────────────────────────────────
BASE_URL = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/"
    "master/csse_covid_19_data/csse_covid_19_daily_reports/"
)


def download_csv(target_date: date) -> pd.DataFrame:
    """
    Bronze layer — download and land data EXACTLY as received.

    Rules:
    - No renaming columns
    - No dropping columns
    - No filling nulls
    - No transforming values
    - Only _metadata columns are added (prefixed with _)
    """
    # Johns Hopkins filenames use MM-DD-YYYY format
    filename = target_date.strftime("%m-%d-%Y") + ".csv"
    url = BASE_URL + filename

    resp = requests.get(url)

    if resp.status_code != 200:
        print(f"  ⚠️  Skipping {filename} — not found (status {resp.status_code})")
        return None

    # Read EXACTLY as received — no touching
    df = pd.read_csv(StringIO(resp.text))

    # ── Only metadata additions are acceptable in Bronze ──
    # _prefix signals: "we added this, it was not in the source"
    df["_report_date"] = target_date          # which day this file belongs to
    df["_source_file"]  = filename             # which file it came from
    df["_ingested_at"]  = pd.Timestamp.now()   # when we downloaded it

    return df


if __name__ == "__main__":
    # Start from the real first day.
    # Safe because we are NOT concatting — each file is saved individually.
    # Silver will handle the schema differences between early and late files.
    start = date(2020, 1, 22)   # first day Johns Hopkins published data
    end   = date(2023, 3, 10)   # last day before they shut the repo down

    # Create output folder
    os.makedirs("data/bronze", exist_ok=True)

    d          = start
    total_days = (end - start).days + 1
    saved      = 0

    print(f"📥 Downloading {total_days} days ({start} → {end})...\n")

    while d <= end:
        df = download_csv(d)
        if df is not None:
            # Save each day as its own individual file — NO concat in Bronze
            # This preserves each file's original schema exactly as Johns Hopkins sent it
            out_path = f"data/bronze/{d.strftime('%m-%d-%Y')}.csv"
            df.to_csv(out_path, index=False)
            print(f"  💾 {d.strftime('%m-%d-%Y')}.csv — {len(df)} rows, {len(df.columns)} cols")
            saved += 1
        d += timedelta(days=1)

    print(f"\n✅ Saved {saved} files to data/bronze/")
    print(f"📁 Early files:  6 cols  (old schema)")
    print(f"📁 Later files: 14 cols  (new schema)")
    print(f"   → Silver will normalize these differences")