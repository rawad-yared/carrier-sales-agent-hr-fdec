from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Load, Negotiation
from app.deps import get_db, require_api_key
from app.schemas.offers import EvaluateOfferRequest, EvaluateOfferResponse
from app.services.negotiation import NegotiationInputs, decide

router = APIRouter(tags=["offers"], dependencies=[Depends(require_api_key)])


@router.post("/evaluate-offer", response_model=EvaluateOfferResponse)
def evaluate_offer(
    req: EvaluateOfferRequest,
    db: Session = Depends(get_db),
) -> EvaluateOfferResponse:
    if req.round_number not in (1, 2, 3):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_round",
                "message": f"round_number must be 1, 2, or 3 (got {req.round_number})",
            },
        )
    if req.carrier_offer <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_offer",
                "message": f"carrier_offer must be positive (got {req.carrier_offer})",
            },
        )

    load = db.get(Load, req.load_id)
    if load is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "load_not_found", "message": f"no load with id {req.load_id}"},
        )

    last_counter: Decimal | None = None
    if req.round_number > 1:
        prev_stmt = (
            select(Negotiation)
            .where(Negotiation.session_id == req.session_id)
            .where(Negotiation.round_number == req.round_number - 1)
            .order_by(Negotiation.id.desc())
            .limit(1)
        )
        prev = db.execute(prev_stmt).scalar_one_or_none()
        if prev and prev.counter_price is not None:
            last_counter = prev.counter_price

    settings = get_settings()
    decision = decide(
        NegotiationInputs(
            loadboard_rate=load.loadboard_rate,
            carrier_offer=req.carrier_offer,
            round_number=req.round_number,
            last_counter=last_counter,
            floor_pct=Decimal(str(settings.floor_pct)),
            target_pct=Decimal(str(settings.target_pct)),
        )
    )

    db.add(
        Negotiation(
            session_id=req.session_id,
            load_id=req.load_id,
            round_number=req.round_number,
            carrier_offer=req.carrier_offer,
            action=decision.action,
            counter_price=decision.counter_price,
            reasoning=decision.reasoning,
        )
    )
    db.commit()

    return EvaluateOfferResponse(
        action=decision.action,
        counter_price=decision.counter_price,
        round_number=req.round_number,
        reasoning=decision.reasoning,
        final=decision.final,
    )
