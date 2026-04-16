from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Call, Load
from app.deps import get_db, require_api_key
from app.schemas.calls import Outcome, Sentiment
from app.schemas.metrics import (
    EquipmentBreakdownRow,
    MetricsByEquipmentResponse,
    MetricsSummaryResponse,
)

router = APIRouter(tags=["metrics"], dependencies=[Depends(require_api_key)])

ALL_OUTCOMES: tuple[str, ...] = (
    "booked",
    "carrier_declined",
    "broker_declined",
    "no_match",
    "carrier_ineligible",
    "abandoned",
    "error",
)
ALL_SENTIMENTS: tuple[str, ...] = ("positive", "neutral", "negative")


@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
def metrics_summary(
    since: datetime | None = Query(default=None),
    include_errors: bool = Query(
        default=False,
        description=(
            "Include outcome='error' calls in aggregates. Defaults to False so "
            "spurious failures (e.g. browser tab-switch mid-call) do not inflate "
            "total_calls or estimated_rep_hours_saved on the demo dashboard. Set "
            "true for raw diagnostic counts."
        ),
    ),
    db: Session = Depends(get_db),
) -> MetricsSummaryResponse:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=30)

    base_filters = [Call.started_at >= since]
    if not include_errors:
        base_filters.append(Call.outcome != "error")

    total = db.execute(
        select(func.count()).select_from(Call).where(*base_filters)
    ).scalar_one()

    outcome_rows = db.execute(
        select(Call.outcome, func.count())
        .where(*base_filters)
        .group_by(Call.outcome)
    ).all()
    outcomes: dict[str, int] = {o: 0 for o in ALL_OUTCOMES}
    for name, count in outcome_rows:
        outcomes[name] = count

    sentiment_rows = db.execute(
        select(Call.sentiment, func.count())
        .where(*base_filters)
        .group_by(Call.sentiment)
    ).all()
    sentiment: dict[str, int] = {s: 0 for s in ALL_SENTIMENTS}
    for name, count in sentiment_rows:
        sentiment[name] = count

    # acceptance_rate per docs/DASHBOARD.md: booked / (booked + carrier_declined + broker_declined)
    # — the fraction of calls that reached a negotiation decision and ended in agreement.
    denom = outcomes["booked"] + outcomes["carrier_declined"] + outcomes["broker_declined"]
    acceptance_rate = (outcomes["booked"] / denom) if denom > 0 else 0.0

    avg_rounds_raw = db.execute(
        select(func.avg(Call.negotiation_rounds)).where(*base_filters)
    ).scalar()
    avg_rounds = float(avg_rounds_raw) if avg_rounds_raw is not None else 0.0

    booked_pairs = db.execute(
        select(Call.final_price, Load.loadboard_rate)
        .join(Load, Call.load_id == Load.load_id)
        .where(
            Call.outcome == "booked",
            Call.started_at >= since,
            Call.final_price.is_not(None),
        )
    ).all()

    if booked_pairs:
        deltas = [(float(fp) - float(lr)) / float(lr) for fp, lr in booked_pairs]
        avg_delta = sum(deltas) / len(deltas)
        total_revenue = sum(float(fp) for fp, _ in booked_pairs)
    else:
        avg_delta = 0.0
        total_revenue = 0.0

    # Agent impact — call time the agent handled without a human rep.
    # Excludes outcome='error' even when include_errors=true, because an
    # errored call would still need a human rep to recover — it isn't time
    # the agent saved. Null duration_seconds rows contribute 0.
    total_duration = db.execute(
        select(func.coalesce(func.sum(Call.duration_seconds), 0)).where(
            Call.started_at >= since,
            Call.outcome != "error",
        )
    ).scalar_one()
    total_duration = int(total_duration or 0)
    rep_hours_saved = total_duration / 3600.0
    labor_rate = get_settings().labor_cost_per_hour_usd
    labor_saved = rep_hours_saved * labor_rate

    # Recoverable declines — carrier walked on price but left on a good tone.
    # These are the single best human-rep callback targets.
    recoverable = db.execute(
        select(func.count())
        .select_from(Call)
        .where(
            Call.started_at >= since,
            Call.outcome == "carrier_declined",
            Call.sentiment.in_(("positive", "neutral")),
        )
    ).scalar_one()

    # Acceptance rate split by sentiment — turns the aimless sentiment
    # distribution into an actionable signal ("negative-sentiment calls
    # close at 8% vs positive at 67% — tone recovery matters").
    # Decisional outcomes are intrinsically non-error so include_errors
    # has no effect here; explicit for clarity.
    sentiment_decision_rows = db.execute(
        select(Call.sentiment, Call.outcome, func.count())
        .where(
            Call.started_at >= since,
            Call.outcome.in_(("booked", "carrier_declined", "broker_declined")),
        )
        .group_by(Call.sentiment, Call.outcome)
    ).all()
    per_sent_booked: dict[str, int] = {s: 0 for s in ALL_SENTIMENTS}
    per_sent_decisional: dict[str, int] = {s: 0 for s in ALL_SENTIMENTS}
    for sent_name, outcome_name, cnt in sentiment_decision_rows:
        per_sent_decisional[sent_name] = per_sent_decisional.get(sent_name, 0) + cnt
        if outcome_name == "booked":
            per_sent_booked[sent_name] = per_sent_booked.get(sent_name, 0) + cnt
    acceptance_by_sentiment = {
        s: (per_sent_booked[s] / per_sent_decisional[s]) if per_sent_decisional[s] > 0 else 0.0
        for s in ALL_SENTIMENTS
    }

    return MetricsSummaryResponse(
        total_calls=total,
        outcomes=outcomes,
        sentiment=sentiment,
        acceptance_rate=float(acceptance_rate),
        avg_negotiation_rounds=avg_rounds,
        avg_delta_from_loadboard=avg_delta,
        total_booked_revenue=total_revenue,
        total_duration_seconds=total_duration,
        estimated_rep_hours_saved=rep_hours_saved,
        estimated_labor_cost_saved_usd=labor_saved,
        labor_cost_per_hour_usd=labor_rate,
        recoverable_declines=int(recoverable or 0),
        acceptance_rate_by_sentiment=acceptance_by_sentiment,
    )


@router.get("/metrics/by-equipment", response_model=MetricsByEquipmentResponse)
def metrics_by_equipment(
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MetricsByEquipmentResponse:
    """Per-equipment acceptance and margin — where is the agent winning?

    Joins calls → loads on load_id, groups by equipment_type. Calls with no
    resolved load (e.g., outcome=no_match, no load_id set) are skipped —
    they have no equipment to attribute.
    """
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=30)

    rows = db.execute(
        select(
            Load.equipment_type,
            Call.outcome,
            Call.final_price,
            Call.negotiation_rounds,
            Load.loadboard_rate,
        )
        .join(Load, Call.load_id == Load.load_id)
        .where(Call.started_at >= since)
    ).all()

    buckets: dict[str, dict] = {}
    for equipment, outcome, final_price, rounds, loadboard_rate in rows:
        b = buckets.setdefault(
            equipment,
            {
                "calls": 0,
                "booked": 0,
                "decisional": 0,
                "deltas": [],
                "booked_rounds": [],
                "revenue": 0.0,
            },
        )
        b["calls"] += 1
        if outcome in ("booked", "carrier_declined", "broker_declined"):
            b["decisional"] += 1
        if outcome == "booked":
            b["booked"] += 1
            if final_price is not None and loadboard_rate is not None and float(loadboard_rate) > 0:
                fp = float(final_price)
                lr = float(loadboard_rate)
                b["deltas"].append((fp - lr) / lr)
                b["revenue"] += fp
            if rounds is not None and rounds > 0:
                b["booked_rounds"].append(int(rounds))

    results: list[EquipmentBreakdownRow] = []
    for equipment, b in sorted(buckets.items()):
        acceptance = (b["booked"] / b["decisional"]) if b["decisional"] > 0 else 0.0
        avg_delta = (sum(b["deltas"]) / len(b["deltas"])) if b["deltas"] else 0.0
        avg_rounds_to_book = (
            sum(b["booked_rounds"]) / len(b["booked_rounds"])
            if b["booked_rounds"]
            else 0.0
        )
        results.append(
            EquipmentBreakdownRow(
                equipment_type=equipment,
                calls=b["calls"],
                booked=b["booked"],
                acceptance_rate=float(acceptance),
                avg_delta_from_loadboard=float(avg_delta),
                avg_rounds_to_book=float(avg_rounds_to_book),
                booked_revenue=float(b["revenue"]),
            )
        )

    return MetricsByEquipmentResponse(results=results)
