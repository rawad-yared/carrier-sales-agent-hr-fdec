import httpx
import streamlit as st

import client
import exec_tab
import ops
import report

RANGE_OPTIONS = [7, 14, 30, 60, 90]
DEFAULT_RANGE_DAYS = 30

st.set_page_config(
    page_title="Acme Logistics — Broker Console",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Card-style polish for st.metric widgets across every tab.
# Use Streamlit's CSS vars so the cards render correctly in both light
# and dark themes — hardcoding #ffffff breaks dark mode (white text on
# white background).
st.markdown(
    """
    <style>
      div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
        padding: 14px 16px;
      }
      div[data-testid="stMetric"] label {
        font-weight: 500;
        font-size: 0.80rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        opacity: 0.75;
      }
      div[data-testid="stMetricValue"] {
        font-weight: 700;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Broker Console — Acme Logistics")
st.caption(
    "Your inbound carrier agent's daily performance and where it needs attention. "
    "**Ops** — audit live calls and surface recoverable declines. "
    "**Exec** — where the agent is winning, where to tune it, and what it's worth. "
    "**Report** — the week in prose, ready to forward."
)

try:
    health = client.health()
    status = health.get("status", "unknown")
    st.caption(f"API: **{status}** · base URL `{client.BASE_URL}`")
except httpx.HTTPError as exc:
    st.error(f"API unreachable at {client.BASE_URL}: {exc}")
    st.stop()

# Shared Exec/Report range selector — lifted to app-level so both tabs
# always pull the same window. Two separate widgets used to drift (Exec
# defaulted 30d, Report 7d) and the labor-savings numbers looked
# inconsistent at a glance.
with st.sidebar:
    st.subheader("Exec / Report range")
    shared_range_days = st.selectbox(
        "Date range",
        options=RANGE_OPTIONS,
        index=RANGE_OPTIONS.index(DEFAULT_RANGE_DAYS),
        format_func=lambda d: f"Last {d} days",
        key="shared_range_days",
    )

ops_pane, exec_pane, report_pane = st.tabs(["Ops", "Exec", "Report"])

with ops_pane:
    ops.render()

with exec_pane:
    exec_tab.render(shared_range_days)

with report_pane:
    report.render(shared_range_days)
