from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Load
from app.deps import get_db, require_api_key
from app.schemas.loads import LoadOut, SearchLoadsRequest, SearchLoadsResponse

router = APIRouter(tags=["loads"], dependencies=[Depends(require_api_key)])


@router.post("/search-loads", response_model=SearchLoadsResponse)
def search_loads(
    req: SearchLoadsRequest,
    db: Session = Depends(get_db),
) -> SearchLoadsResponse:
    stmt = select(Load).where(Load.status == "available")

    if req.origin:
        stmt = stmt.where(Load.origin.ilike(f"%{req.origin}%"))
    if req.destination:
        stmt = stmt.where(Load.destination.ilike(f"%{req.destination}%"))
    if req.equipment_type:
        stmt = stmt.where(Load.equipment_type == req.equipment_type)
    if req.pickup_date:
        stmt = stmt.where(func.date(Load.pickup_datetime) == req.pickup_date)

    stmt = stmt.order_by(Load.pickup_datetime).limit(req.max_results)
    rows = db.execute(stmt).scalars().all()

    return SearchLoadsResponse(
        results=[LoadOut.model_validate(row) for row in rows],
        count=len(rows),
    )
