from tests.conftest import API_KEY

AUTH = {"X-API-Key": API_KEY}


def _log(
    client,
    session_id,
    outcome="booked",
    sentiment="positive",
    load_id="L-9001",
    final_price=None,
    negotiation_rounds=2,
    started_at="2026-04-13T14:00:00Z",
):
    payload = {
        "session_id": session_id,
        "outcome": outcome,
        "sentiment": sentiment,
        "load_id": load_id,
        "negotiation_rounds": negotiation_rounds,
        "started_at": started_at,
        "ended_at": "2026-04-13T14:05:00Z",
    }
    if final_price is not None:
        payload["final_price"] = final_price
    return client.post("/api/log-call", json=payload, headers=AUTH)


def test_by_equipment_empty(client):
    r = client.get(
        "/api/metrics/by-equipment?since=2020-01-01T00:00:00Z", headers=AUTH
    )
    assert r.status_code == 200
    assert r.json() == {"results": []}


def test_by_equipment_requires_api_key(client):
    r = client.get("/api/metrics/by-equipment")
    assert r.status_code == 401


def test_by_equipment_groups_by_load_type(client):
    # L-9001 Dry Van @ $2400, L-9002 Reefer @ $1850 (from seeded_session).
    # Dry Van: 2 booked at 2400 (delta 0), 1 declined → acceptance 2/3.
    # Reefer: 1 booked at 1850 (delta 0) → acceptance 1/1.
    _log(client, "dv1", outcome="booked", load_id="L-9001", final_price=2400.00, negotiation_rounds=1)
    _log(client, "dv2", outcome="booked", load_id="L-9001", final_price=2400.00, negotiation_rounds=3)
    _log(client, "dv3", outcome="carrier_declined", load_id="L-9001", sentiment="negative")
    _log(client, "rf1", outcome="booked", load_id="L-9002", final_price=1850.00, negotiation_rounds=2)

    r = client.get(
        "/api/metrics/by-equipment?since=2020-01-01T00:00:00Z", headers=AUTH
    )
    assert r.status_code == 200
    by_eq = {row["equipment_type"]: row for row in r.json()["results"]}

    assert "Dry Van" in by_eq
    assert "Reefer" in by_eq

    dv = by_eq["Dry Van"]
    assert dv["calls"] == 3
    assert dv["booked"] == 2
    assert abs(dv["acceptance_rate"] - (2 / 3)) < 1e-9
    assert abs(dv["avg_delta_from_loadboard"] - 0.0) < 1e-9
    # Avg rounds to book: (1 + 3) / 2 = 2.0
    assert dv["avg_rounds_to_book"] == 2.0
    assert dv["booked_revenue"] == 4800.00

    rf = by_eq["Reefer"]
    assert rf["calls"] == 1
    assert rf["booked"] == 1
    assert rf["acceptance_rate"] == 1.0
    assert rf["booked_revenue"] == 1850.00


def test_by_equipment_skips_calls_with_no_load(client):
    # Calls with no load_id (e.g., no_match, ineligible) have no equipment
    # to attribute and should be skipped, not crash.
    _log(client, "nomatch", outcome="no_match", load_id=None, sentiment="neutral")
    _log(client, "hit", outcome="booked", load_id="L-9001", final_price=2400.00)

    r = client.get(
        "/api/metrics/by-equipment?since=2020-01-01T00:00:00Z", headers=AUTH
    )
    assert r.status_code == 200
    rows = r.json()["results"]
    assert len(rows) == 1
    assert rows[0]["equipment_type"] == "Dry Van"
    assert rows[0]["calls"] == 1


def test_by_equipment_respects_since_filter(client):
    _log(client, "old", outcome="booked", load_id="L-9001", final_price=2400.00, started_at="2020-01-01T00:00:00Z")
    _log(client, "new", outcome="booked", load_id="L-9002", final_price=1850.00, started_at="2026-04-13T14:00:00Z")

    r = client.get(
        "/api/metrics/by-equipment?since=2026-01-01T00:00:00Z", headers=AUTH
    )
    assert r.status_code == 200
    rows = r.json()["results"]
    assert len(rows) == 1
    assert rows[0]["equipment_type"] == "Reefer"
