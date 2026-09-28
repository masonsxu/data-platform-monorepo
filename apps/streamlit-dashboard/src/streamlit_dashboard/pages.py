"""三个页面: 与 Vue Dashboard 对齐(概览/传感器分析/订单预测), 便于效果对比。"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from streamlit_dashboard import data

DEVICES = [f"D-{i:02d}" for i in range(1, 49)]


def _fmt_int(v: float) -> str:
    return f"{int(v):,}"


def render_overview() -> None:
    days = st.sidebar.selectbox("时间范围(天)", [7, 30, 90], index=1)
    st.title("业务概览")
    ov = data.overview(days)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("订单总量", _fmt_int(ov["daily"]["orders"].sum()))
    c2.metric("总收入(元)", f"{ov['daily']['revenue'].sum() / 1e6:.1f}M")
    c3.metric("接入设备", _fmt_int(ov["sensor"]["total_devices"]))
    c4.metric("设备在线率(全程)", f"{ov['sensor']['online_ratio'] * 100:.1f}%")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=ov["daily"]["date"], y=ov["daily"]["orders"], name="订单量")
    fig.add_scatter(
        x=ov["daily"]["date"],
        y=ov["daily"]["revenue"],
        name="收入",
        yaxis="y2",
        line={"smoothing": 0.4},
    )
    fig.update_layout(
        height=380,
        margin={"t": 30, "b": 20},
        legend={"orientation": "h"},
        yaxis={"title": "订单量"},
        yaxis2={"title": "收入(元)"},
    )
    st.plotly_chart(fig, use_container_width=True)

    cat = ov["categories"]
    fig2 = go.Figure(go.Bar(y=cat["category"], x=cat["revenue"], orientation="h"))
    fig2.update_layout(height=300, margin={"t": 20, "b": 20}, xaxis={"title": "收入(元)"})
    st.plotly_chart(fig2, use_container_width=True)


def render_sensors() -> None:
    st.title("传感器分析")
    device = st.sidebar.selectbox("设备", DEVICES, index=6)
    col1, col2 = st.sidebar.columns(2)
    date_from = col1.date_input("从", value=pd.Timestamp("2025-04-01").date())
    date_to = col2.date_input("到", value=pd.Timestamp("2025-04-30").date())
    z = st.sidebar.slider("异常 z 阈值", 1.5, 4.0, 2.0, 0.1)

    st.caption(f"{device} 小时级温度/电压(数据湖 1244 万行读数按需聚合) · 查询缓存 5 分钟")
    s = data.sensor_series(device, str(date_from), str(date_to))
    if s.empty:
        st.info("该条件下无数据")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_scatter(
        x=s["ts"],
        y=s["temp_min"],
        name="温度下界",
        line={"width": 0},
        showlegend=False,
        hoverinfo="skip",
    )
    fig.add_scatter(
        x=s["ts"],
        y=s["temp_max"],
        name="温度 min-max",
        fill="tonexty",
        fillcolor="rgba(51,112,255,0.15)",
        line={"width": 0},
        hoverinfo="skip",
    )
    fig.add_scatter(x=s["ts"], y=s["temp_avg"], name="均温")
    fig.add_scatter(
        x=s["ts"],
        y=s["voltage_avg"],
        name="电压",
        yaxis="y2",
        line={"width": 1, "color": "#8f3f11"},
    )
    fig.update_layout(
        height=420,
        margin={"t": 30, "b": 20},
        legend={"orientation": "h"},
        yaxis={"title": "温度(C)"},
        yaxis2={"title": "电压(V)"},
    )
    st.plotly_chart(fig, use_container_width=True)

    anom = data.sensor_anomalies(z)
    anom = anom[anom["device_id"] == device]
    st.subheader(f"异常日(z > {z} 且绝对偏离 > 0.5C)")
    if anom.empty:
        st.info("该设备在查询条件下无异常日")
    else:
        st.dataframe(anom, use_container_width=True, hide_index=True)


def render_forecast() -> None:
    st.title("订单预测")
    st.caption(
        "lake/clean/orders(Parquet) → 日聚合 → lag/dow 特征 → HistGradientBoosting"
        "(MLflow: 验证 MAPE 7.5%) → 递归预测 7 天"
    )
    try:
        fc = data.load_forecast()
    except FileNotFoundError:
        st.error("预测产物不存在: 先运行 make predict")
        return

    fig = go.Figure()
    band = fc.dropna(subset=["forecast"])
    fig.add_scatter(
        x=band["ts"],
        y=band["upper"],
        name="预测上界",
        line={"width": 0},
        showlegend=False,
        hoverinfo="skip",
    )
    fig.add_scatter(
        x=band["ts"],
        y=band["lower"],
        name="95% 置信带",
        fill="tonexty",
        fillcolor="rgba(51,112,255,0.15)",
        line={"width": 0},
        hoverinfo="skip",
    )
    fig.add_scatter(x=fc["ts"], y=fc["orders"], name="实际订单", line={"color": "#1f77b4"})
    fig.add_scatter(
        x=fc["ts"],
        y=fc["forecast"],
        name="预测",
        line={"color": "#e02020", "dash": "dash"},
    )
    fig.update_layout(
        height=420,
        margin={"t": 30, "b": 20},
        legend={"orientation": "h"},
        yaxis={"title": "日订单量"},
    )
    st.plotly_chart(fig, use_container_width=True)
