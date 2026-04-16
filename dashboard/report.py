"""Report tab — narrative weekly executive summary.

Auto-generated bullets drawn from the same /api/metrics/summary and
/api/metrics/by-equipment endpoints the Exec tab uses. No new API
surface; the intent is a prose summary a broker VP can read in 30s.
"""
from datetime import datetime, timedelta, timezone

import httpx
import streamlit as st

import client


def render() -> None:
    st.header("Report — Weekly Executive Summary")
    st.caption(
        "A prose readout of what the inbound agent did this week — the things "
        "worth forwarding to the ops lead and the VP. Drill into the Ops or "
        "Exec tab for the underlying data."
    )

    with st.sidebar:
        st.subheader("Report range")
        range_days = st.selectbox(
            "Period",
            options=[7, 14, 30],
            index=0,
            format_func=lambda d: f"Last {d} days",
            key="report_range_days",
        )

    since_dt = datetime.now(timezone.utc) - timedelta(days=range_days)
    prev_since_dt = since_dt - timedelta(days=range_days)

    try:
        metrics = client.metrics_summary(since=since_dt)
        prev_metrics = client.metrics_summary(since=prev_since_dt)
        equipment = client.metrics_by_equipment(since=since_dt)
    except httpx.HTTPError as exc:
        st.error(f"Failed to fetch report data: {exc}")
        return

    total_calls = int(metrics.get("total_calls", 0) or 0)
    if total_calls == 0:
        st.info(
            f"No calls landed in the last {range_days} days. "
            "Once the HappyRobot agent is live, this report populates automatically."
        )
        return

    _render_headline(metrics, range_days)
    st.divider()
    _render_snapshot(metrics)
    st.divider()
    _render_bullets(metrics, prev_metrics, equipment, range_days)
    st.divider()
    _render_footer(metrics, range_days)


def _render_headline(metrics: dict, range_days: int) -> None:
    calls = int(metrics.get("total_calls", 0) or 0)
    booked = int((metrics.get("outcomes") or {}).get("booked", 0) or 0)
    revenue = float(metrics.get("total_booked_revenue", 0) or 0)
    hours_saved = float(metrics.get("estimated_rep_hours_saved", 0) or 0)
    labor_saved = float(metrics.get("estimated_labor_cost_saved_usd", 0) or 0)

    st.success(
        f"In the last **{range_days} days** the agent handled **{calls} inbound calls**, "
        f"booked **{booked}** of them for **\\${revenue:,.0f}** in revenue, and saved an "
        f"estimated **{hours_saved:.0f} rep-hours** (≈ **\\${labor_saved:,.0f}** in loaded "
        f"labor cost). Keep reading for what moved and what to do next."
    )


def _render_snapshot(metrics: dict) -> None:
    st.subheader("Snapshot")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Calls", metrics.get("total_calls", 0))
    c2.metric(
        "Acceptance rate",
        f"{metrics.get('acceptance_rate', 0):.0%}",
        help="Booked ÷ (booked + declined). The true closing rate.",
    )
    c3.metric(
        "Avg margin vs loadboard",
        f"{metrics.get('avg_delta_from_loadboard', 0):+.1%}",
    )
    c4.metric(
        "Booked revenue",
        f"${metrics.get('total_booked_revenue', 0):,.0f}",
    )


def _render_bullets(
    metrics: dict,
    prev_metrics: dict,
    equipment: dict,
    range_days: int,
) -> None:
    st.subheader("What happened, in bullets")
    bullets = _build_bullets(metrics, prev_metrics, equipment, range_days)
    for bullet in bullets:
        st.markdown(f"- {bullet}")


def _build_bullets(
    metrics: dict,
    prev_metrics: dict,
    equipment: dict,
    range_days: int,
) -> list[str]:
    """Pure-data function: generate 4–6 narrative bullets from metrics dicts.

    Kept separate from `_render_bullets` so the text generation is trivial
    to unit-test if we ever want to.
    """
    bullets: list[str] = []

    # 1. Volume vs prior period
    calls_now = int(metrics.get("total_calls", 0) or 0)
    calls_prev = int(prev_metrics.get("total_calls", 0) or 0)
    if calls_prev > 0:
        delta_pct = (calls_now - calls_prev) / calls_prev
        direction = "up" if delta_pct >= 0 else "down"
        bullets.append(
            f"**Call volume {direction} {abs(delta_pct):.0%}** vs the prior {range_days}-day "
            f"window ({calls_now} vs {calls_prev})."
        )

    # 2. Acceptance rate trend
    acc_now = float(metrics.get("acceptance_rate", 0) or 0)
    acc_prev = float(prev_metrics.get("acceptance_rate", 0) or 0)
    if calls_prev > 0:
        pts = (acc_now - acc_prev) * 100
        if abs(pts) >= 1:
            verb = "gained" if pts >= 0 else "lost"
            bullets.append(
                f"**Acceptance {verb} {abs(pts):.0f}pts** ({acc_now:.0%} vs {acc_prev:.0%}). "
                + (
                    "Agent is closing more of what it reaches — lean into it."
                    if pts >= 0
                    else "Investigate margin leakage in the Exec tab's Sankey."
                )
            )
        else:
            bullets.append(
                f"**Acceptance held at {acc_now:.0%}** ({acc_prev:.0%} prior period) — "
                "negotiation policy is stable."
            )

    # 3. Best equipment (highest acceptance with >=3 calls)
    rows = [r for r in equipment.get("results", []) if r.get("calls", 0) >= 3]
    if rows:
        rows.sort(key=lambda r: r.get("acceptance_rate", 0), reverse=True)
        best = rows[0]
        worst = rows[-1]
        bullets.append(
            f"**{best['equipment_type']}** is the strongest equipment "
            f"({best.get('acceptance_rate', 0):.0%} acceptance on "
            f"{best['calls']} calls at {best.get('avg_delta_from_loadboard', 0):+.1%} "
            "margin vs loadboard)."
        )
        if len(rows) > 1 and best["equipment_type"] != worst["equipment_type"]:
            bullets.append(
                f"**{worst['equipment_type']}** is the laggard — only "
                f"{worst.get('acceptance_rate', 0):.0%} acceptance on "
                f"{worst['calls']} calls. Tune the floor for this equipment or "
                "review whether loadboard rates are out of line."
            )

    # 4. Recoverable declines — our prescriptive differentiator
    recoverable = int(metrics.get("recoverable_declines", 0) or 0)
    if recoverable > 0:
        bullets.append(
            f"**{recoverable} recoverable declines** — carriers who walked on "
            "price but left on good terms. Queue them for a human rep callback; "
            "each is a warm lead, not a cold one."
        )

    # 5. Labor savings — the headline value line
    hours = float(metrics.get("estimated_rep_hours_saved", 0) or 0)
    dollars = float(metrics.get("estimated_labor_cost_saved_usd", 0) or 0)
    if hours > 0:
        bullets.append(
            f"**~{hours:.0f} rep-hours saved** (≈ \\${dollars:,.0f} at loaded rate). "
            "That's capacity freed up for outbound, not inbound triage."
        )

    # 6. Margin direction
    margin_now = float(metrics.get("avg_delta_from_loadboard", 0) or 0)
    margin_prev = float(prev_metrics.get("avg_delta_from_loadboard", 0) or 0)
    if calls_prev > 0 and abs(margin_now - margin_prev) >= 0.005:
        pts = (margin_now - margin_prev) * 100
        verb = "expanded" if pts >= 0 else "compressed"
        bullets.append(
            f"**Margin {verb} {abs(pts):.1f}pts** vs prior period "
            f"({margin_now:+.1%} vs {margin_prev:+.1%})."
            + (
                " Good — agent is holding price."
                if pts >= 0
                else " Tighten `FLOOR_PCT` in config if this trend continues."
            )
        )

    if not bullets:
        bullets.append(
            "Not enough volume yet to extract a trend. Widen the period or wait for more calls."
        )
    return bullets


def _render_footer(metrics: dict, range_days: int) -> None:
    outcomes = metrics.get("outcomes") or {}
    total = int(metrics.get("total_calls", 0) or 0)
    parts = []
    for key in ("booked", "carrier_declined", "broker_declined", "no_match", "carrier_ineligible", "abandoned", "error"):
        n = int(outcomes.get(key, 0) or 0)
        if n > 0:
            parts.append(f"{n} {key.replace('_', ' ')}")
    breakdown = ", ".join(parts) if parts else "no outcomes recorded"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.caption(
        f"Period: last {range_days} days · Calls: {total} ({breakdown}) · "
        f"Generated {generated}. Data refreshes every 60s."
    )
