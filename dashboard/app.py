import httpx
import pandas as pd
import streamlit as st

from client import ApiClient

st.set_page_config(page_title="Carrier Sales — Ops", layout="wide")
st.title("Carrier Sales — Ops")
st.caption("Phase 1 stub — proves end-to-end integration: dashboard → API → Postgres.")

client = ApiClient()

with st.sidebar:
    st.header("Filters")
    origin = st.text_input("Origin contains")
    destination = st.text_input("Destination contains")
    equipment = st.selectbox(
        "Equipment",
        options=["", "Dry Van", "Reefer", "Flatbed", "Power Only"],
        index=0,
    )
    max_results = st.slider("Max results", min_value=1, max_value=20, value=10)

try:
    health = client.health()
    st.success(f"API health: {health.get('status')}")
except httpx.HTTPError as e:
    st.error(f"API unreachable: {e}")
    st.stop()

st.subheader("Available loads")

body: dict = {"max_results": max_results}
if origin:
    body["origin"] = origin
if destination:
    body["destination"] = destination
if equipment:
    body["equipment_type"] = equipment

try:
    result = client.search_loads(body)
except httpx.HTTPError as e:
    st.error(f"Failed to fetch loads: {e}")
    st.stop()

loads = result.get("results", [])
st.metric("Matching loads", result.get("count", 0))

if loads:
    df = pd.DataFrame(loads)
    display_cols = [
        "load_id",
        "origin",
        "destination",
        "pickup_datetime",
        "equipment_type",
        "loadboard_rate",
        "miles",
        "commodity_type",
    ]
    st.dataframe(
        df[[c for c in display_cols if c in df.columns]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No loads match the current filters.")
