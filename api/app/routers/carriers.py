import re

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import require_api_key
from app.schemas.carriers import VerifyCarrierRequest, VerifyCarrierResponse
from app.services import fmcsa

router = APIRouter(tags=["carriers"], dependencies=[Depends(require_api_key)])

MC_REGEX = re.compile(r"^\d{1,8}$")


@router.post("/verify-carrier", response_model=VerifyCarrierResponse)
def verify_carrier(req: VerifyCarrierRequest) -> VerifyCarrierResponse:
    mc = req.mc_number.strip()
    if not MC_REGEX.match(mc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_mc_number",
                "message": f"MC number must be 1-8 digits (got {req.mc_number!r})",
            },
        )

    try:
        carrier = fmcsa.lookup_by_mc(mc)
    except fmcsa.FmcsaNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "carrier_not_found", "message": f"no FMCSA record for MC {mc}"},
        )
    except fmcsa.FmcsaUnavailable:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "fmcsa_unavailable",
                "message": "FMCSA upstream error; safe to retry",
            },
        )

    allowed = (carrier.get("allowedToOperate") or "").upper()
    eligible = allowed == "Y"
    dot = carrier.get("dotNumber")

    return VerifyCarrierResponse(
        eligible=eligible,
        mc_number=mc,
        carrier_name=carrier.get("legalName"),
        dot_number=str(dot) if dot else None,
        allowed_to_operate=allowed or None,
        raw_fmcsa_status=carrier.get("statusCode"),
        reason=None if eligible else "not_allowed_to_operate",
    )
