# COVID-19 Case Data Cleansing & Modeling

A small end-to-end data engineering project that:

- Downloads daily COVID-19 case CSVs from the Johns Hopkins CSSE GitHub repository
- Loads them into **Bronze** (raw)
- Cleans/transforms them into **Silver** (standardized + validated)
- Models them into **Gold** (dim/fact schema + analytics-ready views)
- Provides a **Streamlit** dashboard to visualize Gold metrics

The pipeline is orchestrated with an **Airflow** DAG.

---

## Repository structure

- `dags/covid_pipeline.py` - Airflow DAG (bronze → silver → gold)
- `scripts/bronze.py` - download + load raw daily CSVs into `bronze.raw_daily_reports`
- `scripts/silver.py` - clean/normalize raw data into `silver.covid_cases`
- `scripts/gold.py` - build `gold.dim_date`, `gold.dim_location`, and `gold.fact_covid_cases`
- `sql/ddl.sql` - SQL DDL for Bronze/Silver/Gold schemas, tables, and views
- `dashboard/app.py` - Streamlit dashboard reading from `gold` views
- `tests/test_layers.py` - integration tests validating layer constraints
- `docker-compose.yaml` - Postgres + Airflow services

---

## Data model (Bronze → Silver → Gold)

### Bronze (`bronze.raw_daily_reports`)

- One row per record from the downloaded daily CSVs
- Stores raw values as **TEXT** plus ingestion metadata:
  - `_source_file`, `_ingested_at`
- Contains multiple possible column names across the dataset history, unified later.

### Silver (`silver.covid_cases`)

- Standardized schema:
  - `report_date`, `country_region`, `province_state`
  - `confirmed`, `deaths`, `recovered`, `active`
  - `lat`, `long_`, `source_file`
- Normalizations:
  - unify column naming variants
  - normalize country names (mapping)
  - coerce numeric columns, clip negatives to 0
- Validates and removes duplicates on `(report_date, country_region, province_state)`.

### Gold (`gold`)

Star-ish schema:

- `gold.dim_date` (calendar attributes)
- `gold.dim_location` (country + province, with averaged lat/long)
- `gold.fact_covid_cases` with:
  - cumulative measures
  - `new_confirmed`, `new_deaths`
  - `moving_avg_7d` (7-day moving average of new confirmed)

Analytics views:

- `gold.v_global_daily_cases`
- `gold.v_global_cumulative_metrics`
- `gold.v_moving_avg_7d`

---

## Prerequisites

- Docker + Docker Compose
- Python (for local Streamlit/tests if you run them outside containers)

The project assumes environment variables used by the scripts:

- `DB_HOST` (defaults to `localhost`)
- Database credentials are hardcoded in scripts as:
  - `covid_user` / `covid_pass` and database `covid_db`

---

## 1) Create schemas/tables (run DDL)

Create the database structures using `sql/ddl.sql`.

Example (run from your machine with psql tooling, or inside the Postgres container):

```bash
psql "postgresql://covid_user:covid_pass@localhost:5432/covid_db" -f sql/ddl.sql
```

> If you use Docker Compose, Postgres runs on port `5432` as configured.

---

## 2) Start Airflow + Postgres

```bash
docker compose up --build
```

- Postgres (data DB): `covid_postgres`
- Postgres (Airflow metadata DB): `airflow_postgres`
- Airflow webserver: `http://localhost:8080`
- Airflow API server: `http://localhost:8200`

---

## 3) Run the pipeline

Airflow DAG: `covid_daily_bronze`

The DAG runs:

1. Bronze task: `ingest_one_day(logical_date)` downloads and appends one day
2. Silver task: `bronze_to_silver()` processes only new Bronze files
3. Gold task: `silver_to_gold()` processes only new Silver dates

Once containers are up, open Airflow UI:

- `http://localhost:8080`

Enable/trigger the DAG as needed.

---

## 4) Dashboard (Streamlit)

The dashboard reads from Gold views:

- `gold.v_global_daily_cases`
- `gold.v_global_cumulative_metrics`
- `gold.v_moving_avg_7d`

Run (from repository root):

```bash
streamlit run dashboard/app.py
```

Dashboard will be available locally at:

- `http://localhost:8501`

> Note: `dashboard/app.py` uses `DB_URL` with `localhost` for Postgres. If you run Streamlit inside Docker, update `DB_URL` accordingly.

---

## 5) Tests

Integration tests validate constraints in each layer.

Run:

```bash
pytest -q
```

Tests require that Postgres is reachable and that Bronze/Silver/Gold tables exist.

---

## Notes / operational behavior

- **Bronze** is idempotent at the file level (skips `_source_file` already ingested).
- **Silver** and **Gold** are incremental:
  - Silver processes Bronze files not yet cleaned
  - Gold processes Silver dates not yet in `gold.dim_date`
- Airflow tasks rely on `DB_HOST` (set to the Docker service name in `docker-compose.yaml`).

---

## Output

After a successful run, you should be able to query:

- `select * from gold.v_global_daily_cases;`
- `select * from gold.v_global_cumulative_metrics;`
- `select * from gold.v_moving_avg_7d;`

and see the same charts in the Streamlit dashboard.
