from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Call, Load
from app.deps import get_db, require_api_key
from app.schemas.calls import Outcome, Sentiment
from app.schemas.metrics import MetricsSummaryResponse

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
    db: Session = Depends(get_db),
) -> MetricsSummaryResponse:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=30)

    total = db.execute(
        select(func.count()).select_from(Call).where(Call.started_at >= since)
    ).scalar_one()

    outcome_rows = db.execute(
        select(Call.outcome, func.count())
        .where(Call.started_at >= since)
        .group_by(Call.outcome)
    ).all()
    outcomes: dict[str, int] = {o: 0 for o in ALL_OUTCOMES}
    for name, count in outcome_rows:
        outcomes[name] = count

    sentiment_rows = db.execute(
        select(Call.sentiment, func.count())
        .where(Call.started_at >= since)
        .group_by(Call.sentiment)
    ).all()
    sentiment: dict[str, int] = {s: 0 for s in ALL_SENTIMENTS}
    for name, count in sentiment_rows:
        sentiment[name] = count

    booked_count = outcomes["booked"]
    acceptance_rate = (booked_count / total) if total > 0 else 0.0

    avg_rounds_raw = db.execute(
        select(func.avg(Call.negotiation_rounds)).where(Call.started_at >= since)
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

    return MetricsSummaryResponse(
        total_calls=total,
        outcomes=outcomes,
        sentiment=sentiment,
        acceptance_rate=float(acceptance_rate),
        avg_negotiation_rounds=avg_rounds,
        avg_delta_from_loadboard=avg_delta,
        total_booked_revenue=total_revenue,
    )
