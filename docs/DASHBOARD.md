# Dashboard (Streamlit)

> **Status: skeleton.** Fill in as we build.

Two tabs. Both read from the FastAPI backend (`/calls`, `/metrics/summary`) using the shared API key.

## Tab 1: Ops

For the broker watching calls come in. Real-time-ish (polls every 10s).

**Top strip (KPI cards):**
- Calls today
- Active now (started in last 2 min, not ended)
- Booked today
- Acceptance rate today

**Middle: live call feed**
Table of recent calls, newest first. Columns:
- Time
- MC # / Carrier name
- Load ID (link)
- Outcome (color-coded badge)
- Sentiment (emoji + label)
- Final price
- Rounds
- Duration

Click a row → drawer/panel shows transcript + extracted data + negotiation history.

**Filters:** outcome, sentiment, date range.

## Tab 2: Exec

For a broker leader reviewing the program. Daily/weekly/monthly views.

**Top strip (KPI cards):**
- Total calls (period)
- Booked loads (period)
- Acceptance rate (%)
- Avg margin vs loadboard (%)
- Total revenue booked ($)

**Charts:**
- Call volume over time (line, with outcome stacked)
- Outcome distribution (donut)
- Sentiment distribution (donut or bar)
- Avg negotiation rounds by outcome (bar)
- Delta from loadboard distribution (histogram) — how much above/below list we're closing
- Top lanes booked (bar)

**Controls:**
- Date range picker (default last 30 days)
- Compare to previous period toggle

## Implementation notes

- One `app.py`, uses `st.tabs(["Ops", "Exec"])`
- Data layer: small `client.py` module wraps API calls, handles caching with `st.cache_data(ttl=10)` for ops, `ttl=60` for exec
- Charts: Plotly via `st.plotly_chart` (more polish than native Streamlit charts)
- Custom CSS block at top for color palette matching the pitch deck (broker brand colors TBD)

## Metric definitions

| Metric | Definition |
|---|---|
| Acceptance rate | `booked / (booked + carrier_declined + broker_declined)` |
| Avg margin vs loadboard | `mean((final_price - loadboard_rate) / loadboard_rate)` for booked calls. Negative = we conceded. |
| Avg negotiation rounds | `mean(negotiation_rounds)` across all calls that reached the negotiation phase |
| Sentiment split | `count by sentiment / total` |

## Auth

Dashboard sits behind the same ALB with a path-based rule. For the PoC, access is either:
- IP allowlist at the ALB (simplest), or
- Streamlit-native password (`st.secrets["password"]`) — fine for a demo

Pick one when we deploy. Default = IP allowlist for the demo, password fallback if reviewer is on a non-fixed IP.
