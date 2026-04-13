import httpx
import streamlit as st

import client
import exec_tab
import ops

st.set_page_config(
    page_title="Carrier Sales — Broker Console",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Carrier Sales — Broker Console")
st.caption("HappyRobot-powered inbound carrier agent. Live call feed and aggregate metrics.")

try:
    health = client.health()
    status = health.get("status", "unknown")
    st.caption(f"API: **{status}** · base URL `{client.BASE_URL}`")
except httpx.HTTPError as exc:
    st.error(f"API unreachable at {client.BASE_URL}: {exc}")
    st.stop()

ops_pane, exec_pane = st.tabs(["Ops", "Exec"])

with ops_pane:
    ops.render()

with exec_pane:
    exec_tab.render()
