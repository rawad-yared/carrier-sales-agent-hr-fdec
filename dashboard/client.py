"""API client for the dashboard.

Module-level functions so Streamlit's @st.cache_data can decorate them.
TTLs per docs/DASHBOARD.md: 10s for ops data, 60s for exec aggregates.
"""
import os
from datetime import datetime

import httpx
import streamlit as st

BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000").rstrip("/")
API_KEY = os.environ.get("DASHBOARD_API_KEY", "")

_TIMEOUT = httpx.Timeout(10.0)


def _headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def health() -> dict:
    r = httpx.get(f"{BASE_URL}/api/health", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=10)
def list_calls(
    limit: int = 100,
    offset: int = 0,
    outcome: str | None = None,
    since: datetime | None = None,
) -> dict:
    params: dict = {"limit": limit, "offset": offset}
    if outcome:
        params["outcome"] = outcome
    since_iso = _iso(since)
    if since_iso:
        params["since"] = since_iso
    r = httpx.get(f"{BASE_URL}/api/calls", params=params, headers=_headers(), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
def search_loads_all() -> dict:
    """Fetch the full load board (cached for 5 min). Used by exec tab to
    join loadboard_rate and lane strings onto calls client-side.
    """
    r = httpx.post(
        f"{BASE_URL}/api/search-loads",
        json={"max_results": 500},
        headers=_headers(),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=60)
def metrics_summary(since: datetime | None = None) -> dict:
    params: dict = {}
    since_iso = _iso(since)
    if since_iso:
        params["since"] = since_iso
    r = httpx.get(
        f"{BASE_URL}/api/metrics/summary",
        params=params,
        headers=_headers(),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()
