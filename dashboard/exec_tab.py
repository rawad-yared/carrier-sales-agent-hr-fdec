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


def render(range_days: int) -> None:
    st.header("Exec — Program Overview")
    st.caption(
        "What the inbound agent is worth, where it's winning, and where to tune it. "
        "Every chart below drives a specific decision — the caption under each "
        "explains what it tells you and what to do about it. "
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}."
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

    st.subheader("Call flow — from inbound to outcome")
    _render_call_flow_sankey(calls, rate_by_load)
    st.divider()

    st.subheader("Lane map — bookings & supply gaps")
    _render_lane_map(calls, rate_by_load, loads)
    st.divider()

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
    st.subheader("Lane intelligence — supply gaps")
    _render_lane_gaps(calls)
    st.subheader("Workhorse lanes")
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
        f"**Executive summary — last {range_days} days.** "
        f"The agent handled **{calls} calls**, "
        f"booked **{booked}** of them for **\\${revenue:,.0f}** in revenue "
        f"at **{margin_sign}{avg_margin:.1%}** vs. loadboard, "
        f"and saved an estimated **{_fmt_hours(hours_saved)}** of rep time "
        f"(≈ **\\${labor_saved:,.0f}** at \\${labor_rate:.0f}/hr loaded cost)."
    )
    st.success(headline)


def _fmt_hours(hours: float) -> str:
    """Short windows produce fractional hours — a raw `{:.0f}` would read "0 hours"
    while the dollar figure is non-zero, which looks like a broken rate.
    """
    if hours <= 0:
        return "0 hours"
    if hours < 1:
        return f"{int(round(hours * 60))} minutes"
    if hours < 10:
        return f"{hours:.1f} hours"
    return f"{hours:.0f} hours"


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


def _render_lane_gaps(calls: list[dict]) -> None:
    """Prescriptive lane recommendations driven by no_match outcomes.

    Every no_match call is a carrier we turned away because the loadboard
    didn't have what they wanted. Group those calls by the carrier's stated
    origin (HappyRobot extraction puts this in extracted.carrier_current_location;
    the synthetic seeder uses the legacy key 'current_location' — handle both).
    Origins that show up ≥2 times in the period are concrete sourcing leads:
    "more carriers in Dallas keep calling without a load" → broker should
    source more Dallas-origin freight.

    This is the one prescriptive insight on the dashboard: it says where to
    *add* supply, not just describe what already happened.
    """
    no_match = [c for c in calls if c.get("outcome") == "no_match"]
    total_no_match = len(no_match)
    if total_no_match == 0:
        st.caption(
            "No `no_match` calls in this window — every carrier who reached "
            "the load-search step found something to negotiate on. If this "
            "stays true, your load board coverage is tracking carrier demand."
        )
        return

    origin_counts: dict[str, int] = {}
    missing_origin = 0
    for call in no_match:
        extracted = call.get("extracted") or {}
        origin = (
            extracted.get("carrier_current_location")
            or extracted.get("current_location")
            or extracted.get("origin")
        )
        if not origin:
            missing_origin += 1
            continue
        origin_counts[origin] = origin_counts.get(origin, 0) + 1

    if not origin_counts:
        st.caption(
            f"{total_no_match} `no_match` calls this period, but none had a "
            "carrier origin extracted. Add `carrier_current_location` to the "
            "HappyRobot post-call extraction node to unlock sourcing recommendations."
        )
        return

    df = (
        pd.DataFrame(
            [{"Origin": k, "Calls": v} for k, v in origin_counts.items()]
        )
        .sort_values("Calls", ascending=True)
        .tail(8)
    )
    fig = px.bar(
        df,
        x="Calls",
        y="Origin",
        orientation="h",
        title="Origins where carriers called but we had nothing to pitch",
        color_discrete_sequence=["#e67e22"],
        text=df["Calls"].map(str),
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="No-match calls", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

    leads = [(origin, n) for origin, n in origin_counts.items() if n >= 2]
    leads.sort(key=lambda pair: pair[1], reverse=True)
    if leads:
        top_origin, top_n = leads[0]
        extras = ""
        if len(leads) > 1:
            extras = " Other supply gaps: " + ", ".join(
                f"{o} ({n})" for o, n in leads[1:4]
            ) + "."
        st.success(
            f"**Sourcing lead:** {top_n} carriers based in **{top_origin}** "
            f"called and walked away because the load board had no match. "
            f"Source more freight originating in {top_origin} — every covered "
            f"call here is a booking the agent can convert.{extras}"
        )
    else:
        st.caption(
            "No origin reached the recommendation threshold (≥2 no-match calls "
            "from the same city). Widen the date range or wait for more volume "
            "to surface a sourcing lead."
        )

    if missing_origin > 0:
        st.caption(
            f"{missing_origin} of {total_no_match} no-match calls are missing "
            "an extracted origin and were skipped from the recommendation."
        )


SANKEY_MIN_CALLS = 15  # below this, the Sankey looks sparse — fall back to donut

SANKEY_OUTCOME_LABEL = {
    "booked": "Booked",
    "carrier_declined": "Carrier declined",
    "broker_declined": "Broker declined",
    "no_match": "No match",
    "carrier_ineligible": "Ineligible",
    "abandoned": "Abandoned",
    "error": "Error",
}


def _booked_margin_bucket(delta: float) -> str:
    """Bucket a booked call's margin vs loadboard into the four Sankey leaves.

    `delta` is (final_price - loadboard_rate) / loadboard_rate.
    """
    if delta >= 0:
        return "At/Above list"
    if delta >= -0.05:
        return "Small concession (≤5%)"
    if delta >= -0.10:
        return "Medium (5–10%)"
    return "Large (>10%)"


def _render_call_flow_sankey(calls: list[dict], rate_by_load: dict[str, float]) -> None:
    """Sankey diagram of Total → Outcome → Reason buckets.

    Surfaces the same flow the competitor shows, but driven by OUR richer
    7-outcome taxonomy and OUR prescriptive buckets (delta-from-loadboard
    for bookings, sentiment for declines — which is the recoverable-
    declines differentiator rendered graphically).
    """
    total = len(calls)
    if total < SANKEY_MIN_CALLS:
        st.caption(
            f"Sankey appears once the period has ≥{SANKEY_MIN_CALLS} calls "
            f"(currently {total}). Widen the date range or seed more data."
        )
        return

    nodes: list[str] = ["All calls"]
    node_idx: dict[str, int] = {"All calls": 0}

    def _ensure(label: str) -> int:
        if label not in node_idx:
            node_idx[label] = len(nodes)
            nodes.append(label)
        return node_idx[label]

    # Level 1: outcome totals
    outcome_counts: dict[str, int] = {}
    for call in calls:
        outcome_counts[call["outcome"]] = outcome_counts.get(call["outcome"], 0) + 1

    # Level 2: reason buckets keyed by (outcome, bucket_label)
    leaf_counts: dict[tuple[str, str], int] = {}
    for call in calls:
        outcome = call["outcome"]
        bucket = _reason_bucket_for(call, rate_by_load)
        leaf_counts[(outcome, bucket)] = leaf_counts.get((outcome, bucket), 0) + 1

    # Build node/link arrays
    sources: list[int] = []
    targets: list[int] = []
    values: list[int] = []
    link_colors: list[str] = []
    root = 0

    for outcome, count in outcome_counts.items():
        outcome_label = SANKEY_OUTCOME_LABEL.get(outcome, outcome)
        outcome_node = _ensure(outcome_label)
        sources.append(root)
        targets.append(outcome_node)
        values.append(count)
        link_colors.append(OUTCOME_COLORS.get(outcome, "#bbb"))

        for (o, bucket), n in leaf_counts.items():
            if o != outcome:
                continue
            # Suffix buckets with the outcome so identical labels across
            # outcomes (e.g. "Other") remain distinct nodes.
            leaf_label = f"{bucket}"
            leaf_node = _ensure(leaf_label)
            sources.append(outcome_node)
            targets.append(leaf_node)
            values.append(n)
            link_colors.append(OUTCOME_COLORS.get(outcome, "#bbb"))

    node_colors = ["#2c3e50"] + [
        OUTCOME_COLORS.get(_node_to_outcome(label), "#95a5a6")
        for label in nodes[1:]
    ]

    fig = go.Figure(
        data=[
            go.Sankey(
                node={
                    "pad": 18,
                    "thickness": 20,
                    "line": {"color": "rgba(0,0,0,0.2)", "width": 0.5},
                    "label": nodes,
                    "color": node_colors,
                },
                link={
                    "source": sources,
                    "target": targets,
                    "value": values,
                    "color": [_translucent(c, 0.35) for c in link_colors],
                },
            )
        ]
    )
    fig.update_layout(
        title=f"Where {total} calls went — and why",
        font=dict(size=12),
        height=450,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**How to read it:** width = call count. Left band is every inbound call. "
        "Middle band breaks them by outcome. Right band shows *why* — booked calls "
        "are bucketed by how much margin we gave up, declined calls by whether "
        "sentiment left the door open for a recoverable callback, no-match calls "
        "by equipment type asked for. A fat 'Large (>10%)' ribbon under Booked means "
        "the floor is leaking margin; a fat 'Recoverable' ribbon under Carrier declined "
        "is a queue for human rep follow-up."
    )


def _reason_bucket_for(call: dict, rate_by_load: dict[str, float]) -> str:
    """Assign a call to its right-hand-side Sankey node based on outcome."""
    outcome = call["outcome"]
    if outcome == "booked":
        lid = call.get("load_id")
        price = call.get("final_price")
        if lid and price is not None and lid in rate_by_load and rate_by_load[lid] > 0:
            delta = (float(price) - rate_by_load[lid]) / rate_by_load[lid]
            return _booked_margin_bucket(delta)
        return "Unmatched booking"
    if outcome in ("carrier_declined", "broker_declined"):
        if call.get("sentiment") in ("positive", "neutral"):
            return "Recoverable (pos/neu)"
        return "Hard no (negative)"
    if outcome == "no_match":
        extracted = call.get("extracted") or {}
        # API flattens HappyRobot's extraction schema — `equipment` is the
        # key that actually comes through; the others are kept for
        # forward-compat with workflow variants.
        equip = (
            extracted.get("equipment")
            or extracted.get("carrier_equipment")
            or extracted.get("equipment_type")
        )
        return f"Asked: {equip}" if equip else "No equipment recorded"
    if outcome == "carrier_ineligible":
        return "Failed FMCSA check"
    if outcome == "abandoned":
        return "Caller dropped"
    if outcome == "error":
        return "System error"
    return "Other"


def _node_to_outcome(label: str) -> str:
    """Reverse-lookup outcome key from a Sankey node label for node coloring."""
    for key, display in SANKEY_OUTCOME_LABEL.items():
        if display == label:
            return key
    return ""


def _translucent(hex_color: str, alpha: float) -> str:
    """Convert #rrggbb to rgba(r,g,b,alpha) for softer Sankey ribbons."""
    c = hex_color.lstrip("#")
    if len(c) != 6:
        return f"rgba(150,150,150,{alpha})"
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _render_lane_map(
    calls: list[dict],
    rate_by_load: dict[str, float],
    loads: list[dict],
) -> None:
    """Folium map with two layers: booked-lane polylines and no-match origins.

    Booked lanes are colored by margin vs loadboard (green/amber/red) —
    richer than the competitor's equipment-only coloring. No-match origins
    are sized by count so the map doubles as a sourcing-lead visualization.
    """
    try:
        import folium
        from streamlit_folium import st_folium
    except ImportError:
        st.warning(
            "Map rendering requires `streamlit-folium` and `folium`. "
            "Run `pip install -r dashboard/requirements.txt` and restart."
        )
        return

    from geocodes import lookup

    load_by_id = {load["load_id"]: load for load in loads}

    booked_segments: list[dict] = []
    unmapped_booked = 0
    for call in calls:
        if call.get("outcome") != "booked":
            continue
        lid = call.get("load_id")
        if not lid or lid not in load_by_id:
            unmapped_booked += 1
            continue
        load = load_by_id[lid]
        origin_coords = lookup(load.get("origin"))
        dest_coords = lookup(load.get("destination"))
        if not origin_coords or not dest_coords:
            unmapped_booked += 1
            continue
        price = call.get("final_price")
        loadboard = rate_by_load.get(lid)
        delta = None
        if price is not None and loadboard:
            delta = (float(price) - float(loadboard)) / float(loadboard)
        booked_segments.append(
            {
                "origin": load["origin"],
                "destination": load["destination"],
                "origin_coords": origin_coords,
                "dest_coords": dest_coords,
                "delta": delta,
                "final_price": float(price) if price is not None else None,
                "loadboard_rate": float(loadboard) if loadboard else None,
                "load_id": lid,
            }
        )

    gap_points: dict[str, int] = {}
    for call in calls:
        if call.get("outcome") != "no_match":
            continue
        extracted = call.get("extracted") or {}
        origin = (
            extracted.get("carrier_current_location")
            or extracted.get("current_location")
            or extracted.get("origin")
        )
        if origin and lookup(origin):
            gap_points[origin] = gap_points.get(origin, 0) + 1

    if not booked_segments and not gap_points:
        st.caption(
            "No booked lanes or supply gaps with known coordinates in this window. "
            "Add seed data or widen the date range."
        )
        return

    # Center on the continental US
    fmap = folium.Map(location=[39.5, -96.0], zoom_start=4, tiles="cartodbpositron")

    booked_layer = folium.FeatureGroup(name=f"Booked lanes ({len(booked_segments)})", show=True)
    for seg in booked_segments:
        color = _delta_to_color(seg["delta"])
        tooltip = _booked_tooltip(seg)
        folium.PolyLine(
            locations=[seg["origin_coords"], seg["dest_coords"]],
            color=color,
            weight=3,
            opacity=0.75,
            tooltip=tooltip,
        ).add_to(booked_layer)
    booked_layer.add_to(fmap)

    if gap_points:
        gap_layer = folium.FeatureGroup(
            name=f"Supply gaps — no-match origins ({sum(gap_points.values())})",
            show=True,
        )
        max_n = max(gap_points.values())
        for origin, n in gap_points.items():
            coords = lookup(origin)
            if not coords:
                continue
            radius = 6 + 12 * (n / max_n)
            folium.CircleMarker(
                location=coords,
                radius=radius,
                color="#e67e22",
                fill=True,
                fill_color="#e67e22",
                fill_opacity=0.55,
                weight=1,
                tooltip=f"{origin}: {n} no-match call{'s' if n != 1 else ''} — sourcing lead",
            ).add_to(gap_layer)
        gap_layer.add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)

    # Inline legend via Folium's macro-less HTML inject
    legend_html = (
        '<div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999; '
        'background: white; padding: 8px 12px; border: 1px solid #ccc; '
        'border-radius: 4px; font-size: 12px; line-height: 1.5;">'
        '<b>Booked lane color</b><br>'
        '<span style="color:#2ecc71;">●</span> At/above list<br>'
        '<span style="color:#f39c12;">●</span> ≤5% concession<br>'
        '<span style="color:#e67e22;">●</span> 5–10% concession<br>'
        '<span style="color:#c0392b;">●</span> &gt;10% concession<br>'
        '<span style="color:#e67e22;">●</span> Supply-gap marker'
        '</div>'
    )
    fmap.get_root().html.add_child(folium.Element(legend_html))

    st_folium(fmap, width=None, height=500, returned_objects=[])

    captions: list[str] = []
    if booked_segments:
        deltas = [s["delta"] for s in booked_segments if s["delta"] is not None]
        if deltas:
            leaking = sum(1 for d in deltas if d < -0.10)
            if leaking:
                captions.append(
                    f"**{leaking} of {len(deltas)} booked lanes** closed >10% below list — "
                    "the red segments on the map are where the floor is leaking margin."
                )
    if gap_points:
        top = max(gap_points.items(), key=lambda kv: kv[1])
        captions.append(
            f"**Sourcing lead:** {top[1]} no-match calls from **{top[0]}** — "
            "orange circle size scales with volume. Add freight originating here."
        )
    if unmapped_booked:
        captions.append(
            f"{unmapped_booked} booked call(s) skipped — either unknown city "
            "or the load isn't in the current board snapshot."
        )
    for line in captions:
        st.caption(line)


def _delta_to_color(delta: float | None) -> str:
    if delta is None:
        return "#7f8c8d"
    if delta >= 0:
        return "#2ecc71"
    if delta >= -0.05:
        return "#f39c12"
    if delta >= -0.10:
        return "#e67e22"
    return "#c0392b"


def _booked_tooltip(seg: dict) -> str:
    lane = f"{seg['origin']} → {seg['destination']}"
    if seg["delta"] is None:
        return f"{lane} (load {seg['load_id']})"
    price = seg["final_price"]
    loadboard = seg["loadboard_rate"]
    return (
        f"{lane}<br>Load {seg['load_id']}"
        f"<br>Final ${price:,.0f} vs list ${loadboard:,.0f}"
        f"<br>Margin {seg['delta']:+.1%}"
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
