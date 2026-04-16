#!/usr/bin/env python3
"""Seed synthetic call data for the dashboard demo.

Posts ~23 calls to /log-call covering all 7 outcomes and 3 sentiments,
spread over the last 14 days, so the Ops + Exec tabs have visible data.

Usage:
    python scripts/seed_synthetic_calls.py           # posts to localhost:8000
    API_BASE=https://your.domain python scripts/seed_synthetic_calls.py
"""
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_env_file() -> dict[str, str]:
    env_file = REPO_ROOT / ".env"
    out: dict[str, str] = {}
    if not env_file.exists():
        return out
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


_env = _load_env_file()
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY") or _env.get("API_KEY")

if not API_KEY:
    print("ERROR: API_KEY not set — put it in .env or export it.", file=sys.stderr)
    sys.exit(1)

# Loadboard rates in sync with data/loads.json
LOAD_RATES: dict[str, float] = {
    "L-1001": 2400, "L-1002": 1850, "L-1003": 2950, "L-1004": 1200, "L-1005": 1650,
    "L-1006": 3800, "L-1007": 950,  "L-1008": 1400, "L-1009": 850,  "L-1010": 1100,
    "L-1011": 1350, "L-1012": 1050, "L-1013": 1900, "L-1014": 1150, "L-1015": 1450,
    "L-1016": 1250, "L-1017": 2200, "L-1018": 1550, "L-1019": 1350, "L-1020": 1700,
    "L-1021": 1850, "L-1022": 1550, "L-1023": 1100, "L-1024": 1300, "L-1025": 2100,
}
LOAD_IDS = list(LOAD_RATES.keys())

CARRIERS = [
    ("133655", "BLUE RIDGE TRANSPORT"),
    ("456789", "STAR FREIGHT LLC"),
    ("789012", "OVERLAND EXPRESS INC"),
    ("234567", "DELTA LOGISTICS"),
    ("345678", "GRAND TRUCKING CO"),
    ("890123", "PACIFIC FREIGHT"),
    ("567890", "RELIABLE LOGISTICS"),
    ("901234", "MIDWEST HAUL LLC"),
    ("112233", "SOUTHERN STAR CARRIERS"),
]

EQUIPMENT = ["Dry Van", "Reefer", "Flatbed", "Power Only"]
LOCATIONS = ["Dallas, TX", "Atlanta, GA", "Chicago, IL", "Phoenix, AZ", "Denver, CO"]


def _make_call(
    outcome: str,
    sentiment: str,
    *,
    load_id: str | None = None,
    rounds: int = 2,
    days_ago: int = 0,
    hours_offset: int = 0,
) -> dict:
    mc, name = random.choice(CARRIERS)
    started = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_offset)
    duration = random.randint(120, 420)
    ended = started + timedelta(seconds=duration)

    final_price: float | None = None
    if outcome == "booked" and load_id:
        loadboard = LOAD_RATES[load_id]
        delta = random.uniform(-0.07, 0.01)
        final_price = round(loadboard * (1 + delta), 2)

    return {
        "session_id": f"synth-{uuid.uuid4().hex[:10]}",
        "mc_number": mc,
        "carrier_name": name,
        "load_id": load_id,
        "outcome": outcome,
        "sentiment": sentiment,
        "final_price": final_price,
        "negotiation_rounds": rounds,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "ended_at": ended.isoformat().replace("+00:00", "Z"),
        "transcript": (
            f"[{outcome}] synthetic transcript — carrier called about lane, "
            f"{rounds} round(s) of negotiation, outcome {outcome}."
        ),
        "extracted": {
            "carrier_equipment": random.choice(EQUIPMENT),
            # carrier_current_location matches the HappyRobot extraction
            # schema and is what the dashboard's lane-gap panel reads.
            "carrier_current_location": random.choice(LOCATIONS),
        },
    }


def _build_fixture() -> list[dict]:
    random.seed(42)
    calls: list[dict] = []

    # 10 booked — the majority, mostly positive/neutral sentiment
    for _ in range(10):
        calls.append(
            _make_call(
                "booked",
                random.choice(["positive", "positive", "neutral"]),
                load_id=random.choice(LOAD_IDS),
                rounds=random.randint(1, 3),
                days_ago=random.randint(0, 14),
                hours_offset=random.randint(0, 12),
            )
        )

    # 4 carrier_declined — negotiation reached but carrier walked
    for _ in range(4):
        calls.append(
            _make_call(
                "carrier_declined",
                random.choice(["neutral", "negative"]),
                load_id=random.choice(LOAD_IDS),
                rounds=random.randint(2, 3),
                days_ago=random.randint(0, 14),
            )
        )

    # 2 broker_declined — offer was below floor at round 3
    for _ in range(2):
        calls.append(
            _make_call(
                "broker_declined",
                "neutral",
                load_id=random.choice(LOAD_IDS),
                rounds=3,
                days_ago=random.randint(0, 14),
            )
        )

    # 5 no_match — concentrated in Dallas/Atlanta so the lane-intel panel
    # has a concrete sourcing recommendation to surface in the demo.
    no_match_origins = ["Dallas, TX", "Dallas, TX", "Dallas, TX", "Atlanta, GA", "Atlanta, GA"]
    for origin in no_match_origins:
        call = _make_call("no_match", "neutral", load_id=None, rounds=0, days_ago=random.randint(0, 14))
        call["extracted"]["carrier_current_location"] = origin
        calls.append(call)

    # 2 carrier_ineligible
    for _ in range(2):
        calls.append(
            _make_call(
                "carrier_ineligible",
                random.choice(["neutral", "negative"]),
                load_id=None,
                rounds=0,
                days_ago=random.randint(0, 14),
            )
        )

    # 1 abandoned
    calls.append(
        _make_call("abandoned", "neutral", load_id=None, rounds=0, days_ago=random.randint(0, 14))
    )

    # 1 error
    calls.append(
        _make_call("error", "neutral", load_id=None, rounds=0, days_ago=random.randint(0, 14))
    )

    return calls


def main() -> int:
    calls = _build_fixture()
    print(f"→ posting {len(calls)} synthetic calls to {API_BASE}/api/log-call")
    ok = 0
    fails: list[str] = []
    with httpx.Client(timeout=10.0) as http:
        for call in calls:
            resp = http.post(
                f"{API_BASE}/api/log-call",
                json=call,
                headers={"X-API-Key": API_KEY},
            )
            if resp.status_code in (200, 201):
                ok += 1
            else:
                fails.append(f"{resp.status_code} {resp.text[:140]}")

    print(f"  {ok}/{len(calls)} accepted")
    for f in fails:
        print(f"  FAIL: {f}")
    return 0 if ok == len(calls) else 1


if __name__ == "__main__":
    sys.exit(main())
