"""Streamlit Dashboard 入口: uv run streamlit run .../app.py --server.port 8002"""

from __future__ import annotations

import streamlit as st

from streamlit_dashboard import pages

st.set_page_config(page_title="Data Platform Demo (Streamlit)", page_icon="📈", layout="wide")

page = st.navigation(
    [
        st.Page(pages.render_overview, title="概览", icon="📊", default=True),
        st.Page(pages.render_sensors, title="传感器分析", icon="🌡️"),
        st.Page(pages.render_forecast, title="订单预测", icon="🔮"),
    ]
)
page.run()
