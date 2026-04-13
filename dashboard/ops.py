from datetime import date, datetime, timedelta, timezone

import httpx
import pandas as pd
import streamlit as st

import client

OUTCOME_BADGES = {
    "booked": "🟢 Booked",
    "carrier_declined": "🔴 Carrier declined",
    "broker_declined": "🟠 Broker declined",
    "no_match": "⚪ No match",
    "carrier_ineligible": "⚫ Ineligible",
    "abandoned": "🔵 Abandoned",
    "error": "❌ Error",
}

SENTIMENT_BADGES = {
    "positive": "😊 Positive",
    "neutral": "😐 Neutral",
    "negative": "😠 Negative",
}


def _today_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def render() -> None:
    st.header("Ops — Live Call Feed")

    top_bar = st.columns([4, 1])
    with top_bar[1]:
        if st.button("🔄 Refresh", help="Clear cache and re-fetch"):
            client.list_calls.clear()
            client.metrics_summary.clear()
            st.rerun()

    with st.sidebar:
        st.subheader("Ops filters")
        outcome_filter = st.multiselect(
            "Outcome",
            options=list(OUTCOME_BADGES.keys()),
            default=[],
        )
        sentiment_filter = st.multiselect(
            "Sentiment",
            options=["positive", "neutral", "negative"],
            default=[],
        )
        default_since = date.today() - timedelta(days=7)
        date_from = st.date_input("Since", value=default_since)

    since_dt = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)

    try:
        data = client.list_calls(limit=500, since=since_dt)
    except httpx.HTTPError as exc:
        st.error(f"Failed to fetch calls: {exc}")
        return

    calls = data.get("results", [])

    if outcome_filter:
        calls = [c for c in calls if c["outcome"] in outcome_filter]
    if sentiment_filter:
        calls = [c for c in calls if c["sentiment"] in sentiment_filter]

    _render_kpis(calls)
    st.divider()

    if not calls:
        st.info(
            "No calls match the current filters. "
            "Run `python scripts/seed_synthetic_calls.py` to populate the dashboard "
            "with demo data."
        )
        return

    _render_feed_table(calls)
    st.divider()
    _render_drill_down(calls)


def _render_kpis(calls: list[dict]) -> None:
    today = _today_start_utc()
    now_utc = datetime.now(timezone.utc)
    two_min_ago = now_utc - timedelta(minutes=2)

    calls_today = [c for c in calls if _parse_iso(c["started_at"]) >= today]
    active_now = [c for c in calls if _parse_iso(c["started_at"]) >= two_min_ago]
    booked_today = [c for c in calls_today if c["outcome"] == "booked"]
    decisional_today = [
        c for c in calls_today
        if c["outcome"] in ("booked", "carrier_declined", "broker_declined")
    ]
    acceptance_today = (
        len(booked_today) / len(decisional_today) if decisional_today else 0.0
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Calls today", len(calls_today))
    k2.metric("Active now", len(active_now), help="Started in last 2 min")
    k3.metric("Booked today", len(booked_today))
    k4.metric("Acceptance today", f"{acceptance_today:.0%}")


def _render_feed_table(calls: list[dict]) -> None:
    rows = []
    for c in calls:
        started = _parse_iso(c["started_at"])
        ended = _parse_iso(c["ended_at"])
        duration = c.get("duration_seconds") or int((ended - started).total_seconds())
        price = (
            f"${float(c['final_price']):,.0f}" if c.get("final_price") is not None else "—"
        )
        rows.append(
            {
                "Time": started.strftime("%m/%d %H:%M"),
                "MC#": c.get("mc_number") or "—",
                "Carrier": c.get("carrier_name") or "—",
                "Load": c.get("load_id") or "—",
                "Outcome": OUTCOME_BADGES.get(c["outcome"], c["outcome"]),
                "Sentiment": SENTIMENT_BADGES.get(c["sentiment"], c["sentiment"]),
                "Price": price,
                "Rounds": c.get("negotiation_rounds", 0),
                "Duration": f"{duration // 60}m {duration % 60}s",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_drill_down(calls: list[dict]) -> None:
    st.subheader("Drill into a call")
    id_to_call = {c["call_id"]: c for c in calls}
    labels = {
        cid: (
            f"{_parse_iso(c['started_at']).strftime('%m/%d %H:%M')} · "
            f"{c.get('carrier_name') or 'unknown carrier'} · {c['outcome']}"
        )
        for cid, c in id_to_call.items()
    }
    selected = st.selectbox(
        "Pick a call",
        options=list(id_to_call.keys()),
        format_func=lambda cid: labels[cid],
        label_visibility="collapsed",
    )
    if not selected:
        return
    call = id_to_call[selected]

    cols = st.columns(4)
    cols[0].metric("Outcome", OUTCOME_BADGES.get(call["outcome"], call["outcome"]))
    cols[1].metric("Sentiment", SENTIMENT_BADGES.get(call["sentiment"], call["sentiment"]))
    cols[2].metric("Rounds", call.get("negotiation_rounds", 0))
    cols[3].metric(
        "Final price",
        f"${float(call['final_price']):,.2f}"
        if call.get("final_price") is not None
        else "—",
    )

    st.caption(
        f"Call `{call['call_id']}` · session `{call['session_id']}` · "
        f"load `{call.get('load_id') or '—'}`"
    )

    with st.expander("Transcript", expanded=False):
        st.text(call.get("transcript") or "(no transcript)")

    with st.expander("Extracted data (HappyRobot post-call node)", expanded=False):
        st.json(call.get("extracted") or {})
