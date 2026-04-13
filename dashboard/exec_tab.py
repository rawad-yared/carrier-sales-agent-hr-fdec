from datetime import datetime, timedelta, timezone

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import client

OUTCOME_COLORS = {
    "booked": "#2ecc71",
    "carrier_declined": "#e74c3c",
    "broker_declined": "#e67e22",
    "no_match": "#95a5a6",
    "carrier_ineligible": "#34495e",
    "abandoned": "#3498db",
    "error": "#c0392b",
}

SENTIMENT_COLORS = {
    "positive": "#2ecc71",
    "neutral": "#95a5a6",
    "negative": "#e74c3c",
}


def render() -> None:
    st.header("Exec — Program Overview")

    with st.sidebar:
        st.subheader("Exec range")
        range_days = st.selectbox(
            "Date range",
            options=[7, 14, 30, 60, 90],
            index=2,
            format_func=lambda d: f"Last {d} days",
        )

    since_dt = datetime.now(timezone.utc) - timedelta(days=range_days)

    try:
        metrics = client.metrics_summary(since=since_dt)
        raw_calls = client.list_calls(limit=500, since=since_dt)
        raw_loads = client.search_loads_all()
    except httpx.HTTPError as exc:
        st.error(f"Failed to fetch data: {exc}")
        return

    _render_kpis(metrics)
    st.divider()

    calls = raw_calls.get("results", [])
    if not calls:
        st.info("No calls in the selected period. Run the synthetic call seeder to populate.")
        return

    loads = raw_loads.get("results", [])
    rate_by_load = {load["load_id"]: float(load["loadboard_rate"]) for load in loads}
    lane_by_load = {
        load["load_id"]: f"{load['origin']} → {load['destination']}" for load in loads
    }

    df = pd.DataFrame(calls)
    # format="ISO8601" tolerates mixed fractional-second precision across rows
    df["started_at_dt"] = pd.to_datetime(df["started_at"], format="ISO8601")
    df["final_price_f"] = pd.to_numeric(df["final_price"], errors="coerce")

    row1_left, row1_right = st.columns([2, 1])
    with row1_left:
        _render_volume_over_time(df)
    with row1_right:
        _render_outcome_donut(metrics)

    row2_left, row2_right = st.columns(2)
    with row2_left:
        _render_sentiment_donut(metrics)
    with row2_right:
        _render_avg_rounds_by_outcome(df)

    _render_delta_histogram(df, rate_by_load)
    _render_top_lanes(df, lane_by_load)


def _render_kpis(metrics: dict) -> None:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total calls", metrics.get("total_calls", 0))
    k2.metric("Booked", metrics.get("outcomes", {}).get("booked", 0))
    k3.metric("Acceptance rate", f"{metrics.get('acceptance_rate', 0):.0%}")
    k4.metric(
        "Avg margin vs loadboard",
        f"{metrics.get('avg_delta_from_loadboard', 0):+.1%}",
        help="mean((final_price - loadboard_rate) / loadboard_rate) across booked calls",
    )
    k5.metric("Booked revenue", f"${metrics.get('total_booked_revenue', 0):,.0f}")


def _render_volume_over_time(df: pd.DataFrame) -> None:
    df_day = df.copy()
    df_day["date"] = df_day["started_at_dt"].dt.date
    grouped = df_day.groupby(["date", "outcome"]).size().reset_index(name="count")
    fig = px.bar(
        grouped,
        x="date",
        y="count",
        color="outcome",
        color_discrete_map=OUTCOME_COLORS,
        title="Call volume over time",
    )
    fig.update_layout(
        xaxis_title="",
        yaxis_title="Calls",
        legend_title="",
        bargap=0.1,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_outcome_donut(metrics: dict) -> None:
    outcomes = metrics.get("outcomes", {})
    filtered = {k: v for k, v in outcomes.items() if v > 0}
    if not filtered:
        st.caption("No outcomes to plot.")
        return
    fig = go.Figure(
        data=[
            go.Pie(
                labels=list(filtered.keys()),
                values=list(filtered.values()),
                hole=0.5,
                marker={"colors": [OUTCOME_COLORS.get(k, "#bbb") for k in filtered]},
            )
        ]
    )
    fig.update_layout(title="Outcome distribution")
    st.plotly_chart(fig, use_container_width=True)


def _render_sentiment_donut(metrics: dict) -> None:
    sentiment = metrics.get("sentiment", {})
    filtered = {k: v for k, v in sentiment.items() if v > 0}
    if not filtered:
        st.caption("No sentiment data.")
        return
    fig = go.Figure(
        data=[
            go.Pie(
                labels=list(filtered.keys()),
                values=list(filtered.values()),
                hole=0.5,
                marker={"colors": [SENTIMENT_COLORS.get(k, "#bbb") for k in filtered]},
            )
        ]
    )
    fig.update_layout(title="Sentiment distribution")
    st.plotly_chart(fig, use_container_width=True)


def _render_avg_rounds_by_outcome(df: pd.DataFrame) -> None:
    grouped = (
        df.groupby("outcome")["negotiation_rounds"]
        .mean()
        .reset_index()
        .sort_values("negotiation_rounds", ascending=False)
    )
    fig = px.bar(
        grouped,
        x="outcome",
        y="negotiation_rounds",
        color="outcome",
        color_discrete_map=OUTCOME_COLORS,
        title="Avg negotiation rounds by outcome",
    )
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Avg rounds")
    st.plotly_chart(fig, use_container_width=True)


def _render_delta_histogram(df: pd.DataFrame, rate_by_load: dict[str, float]) -> None:
    booked = df[(df["outcome"] == "booked") & (df["final_price_f"].notna())]
    deltas = []
    for _, row in booked.iterrows():
        lid = row.get("load_id")
        if lid and lid in rate_by_load and rate_by_load[lid] > 0:
            deltas.append((row["final_price_f"] - rate_by_load[lid]) / rate_by_load[lid])
    if not deltas:
        st.caption("No booked calls matched to seeded loads — delta histogram unavailable.")
        return
    fig = px.histogram(
        x=deltas,
        nbins=15,
        title=f"Margin vs loadboard — distribution ({len(deltas)} booked)",
        labels={"x": "Delta"},
    )
    fig.update_xaxes(tickformat=".0%")
    fig.update_layout(showlegend=False, yaxis_title="Calls", bargap=0.05)
    st.plotly_chart(fig, use_container_width=True)


def _render_top_lanes(df: pd.DataFrame, lane_by_load: dict[str, str]) -> None:
    booked = df[(df["outcome"] == "booked") & (df["load_id"].notna())]
    if booked.empty:
        return
    booked = booked.copy()
    booked["lane"] = booked["load_id"].map(lambda lid: lane_by_load.get(lid, lid))
    counts = (
        booked.groupby("lane")
        .size()
        .reset_index(name="bookings")
        .sort_values("bookings", ascending=True)
        .tail(10)
    )
    fig = px.bar(
        counts,
        x="bookings",
        y="lane",
        orientation="h",
        title="Top lanes booked",
        color_discrete_sequence=["#2ecc71"],
    )
    fig.update_layout(xaxis_title="Bookings", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)
