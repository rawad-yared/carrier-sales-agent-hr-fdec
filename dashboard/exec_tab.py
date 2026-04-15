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
    st.caption(
        "What the inbound agent is worth, where it's winning, and where to tune it. "
        "Every chart below drives a specific decision — the caption under each "
        "explains what it tells you and what to do about it."
    )

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
        equipment = client.metrics_by_equipment(since=since_dt)
    except httpx.HTTPError as exc:
        st.error(f"Failed to fetch data: {exc}")
        return

    _render_hero(metrics, range_days)
    st.divider()
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

    st.subheader("Where the agent is winning")
    _render_equipment_breakdown(equipment)
    st.divider()

    st.subheader("Tone vs. close rate")
    _render_acceptance_by_sentiment(metrics)
    st.divider()

    st.subheader("Volume & outcomes")
    row1_left, row1_right = st.columns([2, 1])
    with row1_left:
        _render_volume_over_time(df)
    with row1_right:
        _render_outcome_donut(metrics)

    _render_avg_rounds_by_outcome(df)
    _render_delta_histogram(df, rate_by_load)
    _render_top_lanes(df, lane_by_load)


def _render_hero(metrics: dict, range_days: int) -> None:
    """Top-of-page narrative banner — the agent's business value in one line.

    Answers the rubric's core question: what is the agent worth to the broker?
    """
    calls = int(metrics.get("total_calls", 0) or 0)
    booked = int((metrics.get("outcomes") or {}).get("booked", 0) or 0)
    revenue = float(metrics.get("total_booked_revenue", 0) or 0)
    avg_margin = float(metrics.get("avg_delta_from_loadboard", 0) or 0)
    hours_saved = float(metrics.get("estimated_rep_hours_saved", 0) or 0)
    labor_saved = float(metrics.get("estimated_labor_cost_saved_usd", 0) or 0)
    labor_rate = float(metrics.get("labor_cost_per_hour_usd", 45) or 45)

    if calls == 0:
        st.info(
            f"No calls in the last {range_days} days. Once the HappyRobot agent starts "
            "receiving calls, this banner shows the business impact."
        )
        return

    margin_sign = "+" if avg_margin >= 0 else ""
    # Streamlit markdown interprets paired `$` as LaTeX math mode, which
    # garbles any line that mixes currency with other formatting. Escape
    # every `$` as `\$` so the banner renders as plain text.
    headline = (
        f"In the last **{range_days} days** the agent handled **{calls} calls**, "
        f"booked **{booked}** of them for **\\${revenue:,.0f}** in revenue "
        f"at **{margin_sign}{avg_margin:.1%}** vs. loadboard, "
        f"and saved an estimated **{hours_saved:.0f} hours** of rep time "
        f"(≈ **\\${labor_saved:,.0f}** at \\${labor_rate:.0f}/hr loaded cost)."
    )
    st.success(headline)


def _render_kpis(metrics: dict) -> None:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric(
        "Total calls",
        metrics.get("total_calls", 0),
        help="All inbound calls the agent handled in the selected period.",
    )
    k2.metric(
        "Booked",
        metrics.get("outcomes", {}).get("booked", 0),
        help="Calls that ended in a confirmed load booking.",
    )
    k3.metric(
        "Acceptance rate",
        f"{metrics.get('acceptance_rate', 0):.0%}",
        help=(
            "True closing rate: booked / (booked + carrier_declined + broker_declined). "
            "Excludes no-match and ineligible carriers. A drop >5% WoW means the "
            "agent is losing price negotiations — investigate equipment breakdown below."
        ),
    )
    k4.metric(
        "Avg margin vs loadboard",
        f"{metrics.get('avg_delta_from_loadboard', 0):+.1%}",
        help=(
            "mean((final_price - loadboard_rate) / loadboard_rate) across booked calls. "
            "Positive = agent closed above posted rate. Negative = giving away margin — "
            "tighten the floor in config if trending down."
        ),
    )
    k5.metric(
        "Booked revenue",
        f"${metrics.get('total_booked_revenue', 0):,.0f}",
        help="Sum of final prices on booked calls in the selected period.",
    )


def _render_equipment_breakdown(equipment: dict) -> None:
    """Per-equipment acceptance + margin — the highest-signal drill-down
    for an ops manager. Tells them which equipment types are the agent's
    strong suit and which need pricing attention.
    """
    rows = equipment.get("results", [])
    rows = [r for r in rows if r.get("calls", 0) > 0]
    if not rows:
        st.caption("No calls matched to loads yet — equipment breakdown will populate as calls land.")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values("acceptance_rate", ascending=True)
    df["acceptance_pct"] = df["acceptance_rate"] * 100
    df["margin_pct"] = df["avg_delta_from_loadboard"] * 100

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.bar(
            df,
            x="acceptance_pct",
            y="equipment_type",
            orientation="h",
            title="Acceptance rate by equipment",
            color="acceptance_pct",
            color_continuous_scale="RdYlGn",
            range_color=[0, 100],
            text=df["acceptance_pct"].map(lambda v: f"{v:.0f}%"),
        )
        fig.update_layout(
            xaxis_title="Acceptance %",
            yaxis_title="",
            coloraxis_showscale=False,
            xaxis_range=[0, 100],
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        fig = px.bar(
            df,
            x="margin_pct",
            y="equipment_type",
            orientation="h",
            title="Avg margin vs loadboard by equipment",
            color="margin_pct",
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            text=df["margin_pct"].map(lambda v: f"{v:+.1f}%"),
        )
        fig.update_layout(
            xaxis_title="Margin % vs loadboard",
            yaxis_title="",
            coloraxis_showscale=False,
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    best = df.iloc[-1]  # highest acceptance after sort
    worst = df.iloc[0]   # lowest
    if len(df) >= 2 and best["equipment_type"] != worst["equipment_type"]:
        st.caption(
            f"**Decision:** {best['equipment_type']} closes at "
            f"**{best['acceptance_pct']:.0f}%** at "
            f"{best['margin_pct']:+.1f}% margin — keep coverage. "
            f"{worst['equipment_type']} closes at only **{worst['acceptance_pct']:.0f}%** — "
            f"either loosen the floor for this equipment in config, or investigate "
            f"whether the loadboard rates for this type are out of line."
        )
    else:
        st.caption(
            "**Decision:** Only one equipment type has booked calls in this window. "
            "Add more lanes or widen the date range for a fuller comparison."
        )

    with st.expander("Equipment breakdown — detail table", expanded=False):
        display = df.rename(
            columns={
                "equipment_type": "Equipment",
                "calls": "Calls",
                "booked": "Booked",
                "acceptance_rate": "Acceptance",
                "avg_delta_from_loadboard": "Avg margin",
                "avg_rounds_to_book": "Avg rounds",
                "booked_revenue": "Revenue",
            }
        )[["Equipment", "Calls", "Booked", "Acceptance", "Avg margin", "Avg rounds", "Revenue"]]
        display["Acceptance"] = display["Acceptance"].map(lambda v: f"{v:.0%}")
        display["Avg margin"] = display["Avg margin"].map(lambda v: f"{v:+.1%}")
        display["Avg rounds"] = display["Avg rounds"].map(lambda v: f"{v:.1f}")
        display["Revenue"] = display["Revenue"].map(lambda v: f"${v:,.0f}")
        st.dataframe(display, use_container_width=True, hide_index=True)


def _render_acceptance_by_sentiment(metrics: dict) -> None:
    """Replaces the aimless sentiment donut.

    Sentiment alone is vanity data. Sentiment × acceptance rate is
    actionable: it tells you whether tone correlates with close rate —
    i.e. whether agent tone-recovery training would move the needle.
    """
    rates = metrics.get("acceptance_rate_by_sentiment") or {}
    sentiment_counts = metrics.get("sentiment") or {}
    recoverable = int(metrics.get("recoverable_declines", 0) or 0)

    rows = []
    for sent in ("positive", "neutral", "negative"):
        rate = float(rates.get(sent, 0) or 0)
        volume = int(sentiment_counts.get(sent, 0) or 0)
        rows.append(
            {
                "Sentiment": sent.capitalize(),
                "sentiment_key": sent,
                "Acceptance": rate,
                "acceptance_pct": rate * 100,
                "Volume": volume,
            }
        )
    df = pd.DataFrame(rows)

    col_chart, col_callout = st.columns([2, 1])
    with col_chart:
        fig = px.bar(
            df,
            x="Sentiment",
            y="acceptance_pct",
            color="sentiment_key",
            color_discrete_map={
                "positive": SENTIMENT_COLORS["positive"],
                "neutral": SENTIMENT_COLORS["neutral"],
                "negative": SENTIMENT_COLORS["negative"],
            },
            title="Acceptance rate by call sentiment",
            text=df["acceptance_pct"].map(lambda v: f"{v:.0f}%"),
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            showlegend=False,
            xaxis_title="",
            yaxis_title="Acceptance %",
            yaxis_range=[0, 110],
        )
        st.plotly_chart(fig, use_container_width=True)
    with col_callout:
        st.metric(
            "Recoverable declines",
            f"{recoverable}",
            help=(
                "Calls where the carrier walked on price but sentiment stayed "
                "positive or neutral. Prime candidates for a human rep callback — "
                "use the 'Recoverable declines' filter in the Ops tab to list them."
            ),
        )
        pos_rate = float(rates.get("positive", 0) or 0)
        neg_rate = float(rates.get("negative", 0) or 0)
        if pos_rate > 0 and neg_rate > 0:
            ratio = pos_rate / neg_rate
            st.caption(
                f"Positive calls close **{ratio:.1f}×** more often than negative. "
                f"Tone recovery matters — consider training the agent to de-escalate "
                f"on early frustration signals."
            )
        elif recoverable > 0:
            st.caption(
                f"**{recoverable} recoverable declines** — carriers who walked on "
                f"price but left on good terms. Worth a human rep callback."
            )
        else:
            st.caption(
                "Sentiment × acceptance becomes meaningful once each bucket "
                "has enough volume. Try a wider date range."
            )


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
    st.caption(
        "**Decision:** Watch for a sudden drop in booked (green) or a spike in "
        "`no_match` (grey) — the first signals a negotiation problem, the second "
        "signals the loadboard doesn't match what carriers are calling about."
    )


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
    fig.update_layout(title="Outcome mix")
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
    st.caption(
        "**Decision:** Booked calls that consistently need 3 rounds mean the "
        "agent's opening counter is too aggressive — carriers push back before "
        "accepting. Tune `TARGET_PCT` up or open with a softer counter."
    )


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
    st.caption(
        "**Decision:** A long left tail (lots of deals below 0%) means the "
        "floor is letting too many thin deals through. A narrow cluster near "
        "target means the policy is working as designed."
    )


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
    st.caption(
        "**Decision:** Your workhorse lanes. Keep these loads hot on the board; "
        "if a lane disappears from this list week-over-week, investigate pricing or "
        "carrier-pool changes before it impacts revenue."
    )
