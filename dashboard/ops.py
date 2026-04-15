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
    st.caption(
        "Every inbound call, ranked newest first. Use the filters to audit "
        "active calls or surface recoverable declines — carriers who walked "
        "on price but left on good terms and are worth a human rep callback."
    )

    top_bar = st.columns([3, 1, 1])
    with top_bar[1]:
        if st.button("📞 Recoverable declines", help="Carrier declined + positive/neutral sentiment. Prime callback targets."):
            st.session_state["ops_preset_recoverable"] = True
            st.session_state["ops_outcome_filter"] = ["carrier_declined"]
            st.session_state["ops_sentiment_filter"] = ["positive", "neutral"]
            st.rerun()
    with top_bar[2]:
        if st.button("🔄 Refresh", help="Clear cache and re-fetch"):
            client.list_calls.clear()
            client.metrics_summary.clear()
            st.session_state.pop("ops_preset_recoverable", None)
            st.rerun()

    with st.sidebar:
        st.subheader("Ops filters")
        outcome_filter = st.multiselect(
            "Outcome",
            options=list(OUTCOME_BADGES.keys()),
            default=st.session_state.get("ops_outcome_filter", []),
            key="ops_outcome_filter",
        )
        sentiment_filter = st.multiselect(
            "Sentiment",
            options=["positive", "neutral", "negative"],
            default=st.session_state.get("ops_sentiment_filter", []),
            key="ops_sentiment_filter",
        )
        default_since = date.today() - timedelta(days=7)
        date_from = st.date_input("Since", value=default_since)
        if st.session_state.get("ops_preset_recoverable"):
            st.success(
                "**Recoverable declines** preset is active. "
                "Showing calls where the agent lost on price but sentiment "
                "stayed positive or neutral."
            )

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

    recoverable_today = [
        c for c in calls_today
        if c["outcome"] == "carrier_declined" and c["sentiment"] in ("positive", "neutral")
    ]

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Calls today", len(calls_today), help="All inbound calls since 00:00 UTC today.")
    k2.metric("Active now", len(active_now), help="Calls that started in the last 2 minutes.")
    k3.metric("Booked today", len(booked_today), help="Calls today that ended in a confirmed booking.")
    k4.metric(
        "Acceptance today",
        f"{acceptance_today:.0%}",
        help="Booked ÷ (booked + declined). Excludes no-match and ineligible carriers — the true closing rate.",
    )
    k5.metric(
        "Recoverable today",
        len(recoverable_today),
        help="Carrier declined on price but sentiment stayed positive/neutral. Use the filter button above to list them.",
    )


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

    _render_negotiation_timeline(call)

    with st.expander("Transcript", expanded=False):
        st.text(call.get("transcript") or "(no transcript)")

    with st.expander("Extracted data (HappyRobot post-call node)", expanded=False):
        st.json(call.get("extracted") or {})


ACTION_BADGES = {
    "accept": "✅ accept",
    "counter": "↩️ counter",
    "reject": "⛔ reject",
}


def _fmt_money(value) -> str:
    if value is None:
        return "—"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _render_negotiation_timeline(call: dict) -> None:
    """Show the per-round offer/counter/reasoning trail for this call.

    This is the visible proof of the agent → policy → dashboard loop:
    each row is one /evaluate-offer call the agent made during the
    conversation, with the exact reasoning the policy returned.
    """
    st.markdown("**Negotiation timeline** — the agent's tool calls to `/evaluate-offer` during this call.")
    try:
        payload = client.call_negotiations(call["call_id"])
    except httpx.HTTPError as exc:
        st.caption(f"Could not load negotiation rounds: {exc}")
        return

    rounds = payload.get("rounds", [])
    if not rounds:
        st.caption("No negotiation rounds recorded for this call (no offers evaluated).")
        return

    rows = []
    for r in rounds:
        rows.append(
            {
                "Round": r.get("round_number"),
                "Carrier offer": _fmt_money(r.get("carrier_offer")),
                "Broker action": ACTION_BADGES.get(r.get("action"), r.get("action") or "—"),
                "Counter": _fmt_money(r.get("counter_price")),
                "Reasoning": r.get("reasoning") or "—",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
