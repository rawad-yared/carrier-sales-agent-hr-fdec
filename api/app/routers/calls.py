import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Call
from app.deps import get_db, require_api_key
from app.schemas.calls import CallOut, CallsListResponse, LogCallRequest, LogCallResponse

router = APIRouter(tags=["calls"], dependencies=[Depends(require_api_key)])


@router.post(
    "/log-call",
    response_model=LogCallResponse,
    status_code=status.HTTP_201_CREATED,
)
def log_call(
    req: LogCallRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LogCallResponse:
    duration = int((req.ended_at - req.started_at).total_seconds())

    existing = db.execute(
        select(Call).where(Call.session_id == req.session_id)
    ).scalar_one_or_none()

    if existing is not None:
        existing.mc_number = req.mc_number
        existing.carrier_name = req.carrier_name
        existing.load_id = req.load_id
        existing.outcome = req.outcome
        existing.sentiment = req.sentiment
        existing.final_price = req.final_price
        existing.negotiation_rounds = req.negotiation_rounds
        existing.started_at = req.started_at
        existing.ended_at = req.ended_at
        existing.duration_seconds = duration
        existing.transcript = req.transcript
        existing.extracted = req.extracted
        db.commit()
        response.status_code = status.HTTP_200_OK
        return LogCallResponse(call_id=existing.call_id, status="updated")

    call = Call(
        call_id=f"c-{uuid.uuid4()}",
        session_id=req.session_id,
        mc_number=req.mc_number,
        carrier_name=req.carrier_name,
        load_id=req.load_id,
        outcome=req.outcome,
        sentiment=req.sentiment,
        final_price=req.final_price,
        negotiation_rounds=req.negotiation_rounds,
        started_at=req.started_at,
        ended_at=req.ended_at,
        duration_seconds=duration,
        transcript=req.transcript,
        extracted=req.extracted,
    )
    db.add(call)
    db.commit()
    return LogCallResponse(call_id=call.call_id, status="logged")


@router.get("/calls", response_model=CallsListResponse)
def list_calls(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    outcome: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> CallsListResponse:
    stmt = select(Call)
    count_stmt = select(func.count()).select_from(Call)

    if outcome:
        stmt = stmt.where(Call.outcome == outcome)
        count_stmt = count_stmt.where(Call.outcome == outcome)
    if since:
        stmt = stmt.where(Call.started_at >= since)
        count_stmt = count_stmt.where(Call.started_at >= since)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(Call.started_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()

    return CallsListResponse(
        results=[CallOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
