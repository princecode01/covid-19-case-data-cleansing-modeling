import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine


DB_URL = "postgresql://covid_user:covid_pass@localhost/covid_db"

engine = create_engine(DB_URL)

@st.cache_data(ttl=3600)
def get_global_daily_cases():
    return pd.read_sql(
        "SELECT * FROM gold.v_global_daily_cases",
        engine
    )

@st.cache_data(ttl=3600)
def get_global_cumulative_metrics():
    return pd.read_sql(
        "SELECT * FROM gold.v_global_cumulative_metrics",
        engine
    )


@st.cache_data(ttl=3600)
def get_moving_avg_7d():
    return pd.read_sql(
        "SELECT * FROM gold.v_moving_avg_7d",
        engine
    )


# Daily new cases
daily_cases = get_global_daily_cases()
fig1 = px.line(daily_cases,x="full_date", y="new_cases", title="Global daily new cases")
st.plotly_chart(fig1, use_container_width=True)

# Cumulative metrics
cumulative_metrics = get_global_cumulative_metrics()
fig2 = px.line(cumulative_metrics,
                  x="full_date",
                  y=["cumulative_cases", "cumulative_deaths","cumulative_recoveries"],
                  title="Global cumulative metrics")
st.plotly_chart(fig2, use_container_width=True)

# 7-day moving average
moving_avg_7d = get_moving_avg_7d()
fig3 = px.line(moving_avg_7d, x="full_date", y="moving_avg_7d", title="Global 7-day moving average of new cases")
st.plotly_chart(fig3, use_container_width=True)

