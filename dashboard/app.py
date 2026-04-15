import httpx
import streamlit as st

import client
import exec_tab
import ops

st.set_page_config(
    page_title="Acme Logistics — Broker Console",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Broker Console — Acme Logistics")
st.caption(
    "Your inbound carrier agent's daily performance and where it needs attention. "
    "**Ops** — audit live calls and surface recoverable declines. "
    "**Exec** — where the agent is winning, where to tune it, and what it's worth."
)

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
