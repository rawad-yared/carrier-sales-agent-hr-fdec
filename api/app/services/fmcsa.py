"""FMCSA QCMobile API client.

Base URL and shape per FMCSA QCMobile public API.
See https://mobile.fmcsa.dot.gov/qc/services
"""
from typing import Any

import httpx

from app.config import get_settings

FMCSA_BASE_URL = "https://mobile.fmcsa.dot.gov/qc/services/carriers"
TIMEOUT_SECONDS = 5.0


class FmcsaError(Exception):
    pass


class FmcsaNotFound(FmcsaError):
    pass


class FmcsaUnavailable(FmcsaError):
    pass


def lookup_by_mc(mc_number: str) -> dict[str, Any]:
    """Look up a carrier by MC docket number.

    Returns the flat `carrier` dict (legalName, dotNumber, allowedToOperate,
    statusCode, ...). Raises `FmcsaNotFound` on 200 with empty content or
    `FmcsaUnavailable` on any network / upstream error.
    """
    settings = get_settings()
    url = f"{FMCSA_BASE_URL}/docket-number/{mc_number}"
    try:
        response = httpx.get(
            url,
            params={"webKey": settings.fmcsa_webkey},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.RequestError as e:
        raise FmcsaUnavailable(f"FMCSA network error: {e}") from e

    if response.status_code >= 500:
        raise FmcsaUnavailable(f"FMCSA returned {response.status_code}")
    if response.status_code != 200:
        raise FmcsaUnavailable(
            f"FMCSA returned {response.status_code}: {response.text[:200]}"
        )

    try:
        body = response.json()
    except ValueError as e:
        raise FmcsaUnavailable(f"FMCSA returned non-JSON body: {e}") from e

    content = body.get("content") or []
    if not content:
        raise FmcsaNotFound(f"no FMCSA record for MC {mc_number}")

    # content can be a list of wrapper dicts each with a "carrier" sub-object,
    # or a single dict. Normalize to the inner carrier record.
    first = content[0] if isinstance(content, list) else content
    carrier = first.get("carrier") if isinstance(first, dict) and "carrier" in first else first
    if not isinstance(carrier, dict):
        raise FmcsaUnavailable("FMCSA response missing carrier object")
    return carrier
