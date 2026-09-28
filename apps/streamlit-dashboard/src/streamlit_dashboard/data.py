"""数据访问层: 进程内直查 Engine(与 Vue 版走 FastAPI 的差异点), 带 Streamlit 缓存。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import streamlit as st
from data_core import queries
from data_core.engine import Engine


@st.cache_resource(show_spinner="连接查询引擎 ...")
def get_engine() -> Engine:
    return Engine()


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    """SQL 结果缓存 5 分钟; Engine 名称拼进 SQL, 集群/湖切换自动失效。"""
    return get_engine().query(sql).to_pandas()


@st.cache_data(ttl=300, show_spinner=False)
def load_forecast() -> pd.DataFrame:
    from data_core.lake import lake_config

    path = Path(lake_config().clean_dir) / "forecast" / "daily_orders_forecast.parquet"
    return (
        pl.read_parquet(path)
        .with_columns(
            pl.col("orders").cast(pl.Float64),
            pl.col("forecast").cast(pl.Float64),
            pl.col("lower").cast(pl.Float64),
            pl.col("upper").cast(pl.Float64),
        )
        .to_pandas()
    )


def overview(days: int) -> dict:
    engine = get_engine().name
    daily = run_query(queries.daily_orders(engine, days)).sort_values("date")
    categories = run_query(queries.category_revenue(engine, days))
    sensor = run_query(queries.sensor_summary(engine)).iloc[0]
    return {"daily": daily, "categories": categories, "sensor": sensor}


def sensor_series(device: str, date_from: str, date_to: str) -> pd.DataFrame:
    engine = get_engine().name
    return run_query(queries.sensor_series(engine, device, date_from, date_to))


def sensor_anomalies(z: float) -> pd.DataFrame:
    return run_query(queries.sensor_anomalies(get_engine().name, z))
