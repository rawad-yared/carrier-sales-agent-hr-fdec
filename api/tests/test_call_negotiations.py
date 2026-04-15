from tests.conftest import API_KEY

AUTH = {"X-API-Key": API_KEY}


def _log(client, session_id, load_id="L-9001"):
    """Log a minimal call with a given session_id + load_id."""
    r = client.post(
        "/api/log-call",
        json={
            "session_id": session_id,
            "outcome": "booked",
            "sentiment": "positive",
            "load_id": load_id,
            "final_price": 2400.00,
            "negotiation_rounds": 2,
            "started_at": "2026-04-13T14:00:00Z",
            "ended_at": "2026-04-13T14:05:00Z",
        },
        headers=AUTH,
    )
    return r.json()["call_id"]


def _offer(client, session_id, round_number, carrier_offer, load_id="L-9001"):
    """Invoke /evaluate-offer — the same way the HappyRobot agent would."""
    return client.post(
        "/api/evaluate-offer",
        json={
            "load_id": load_id,
            "carrier_offer": carrier_offer,
            "round_number": round_number,
            "session_id": session_id,
        },
        headers=AUTH,
    )


def test_call_negotiations_requires_api_key(client):
    r = client.get("/api/calls/c-nope/negotiations")
    assert r.status_code == 401


def test_call_negotiations_404_when_call_missing(client):
    r = client.get("/api/calls/c-nope/negotiations", headers=AUTH)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "call_not_found"


def test_call_negotiations_empty_when_no_offers(client):
    call_id = _log(client, "s-no-offers")

    r = client.get(f"/api/calls/{call_id}/negotiations", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["call_id"] == call_id
    assert body["session_id"] == "s-no-offers"
    assert body["rounds"] == []


def test_call_negotiations_returns_full_timeline(client):
    # L-9001 loadboard = $2400, floor = 0.92 * 2400 = $2208
    # Round 1: offer $2000 (below floor) → counter at target
    # Round 2: offer $2250 (above floor, below target) → counter
    # Round 3: offer $2300 (above floor) → accept
    session_id = "s-timeline"
    _offer(client, session_id, 1, 2000.00)
    _offer(client, session_id, 2, 2250.00)
    _offer(client, session_id, 3, 2300.00)
    call_id = _log(client, session_id)

    r = client.get(f"/api/calls/{call_id}/negotiations", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["call_id"] == call_id
    assert body["session_id"] == session_id
    assert body["load_id"] == "L-9001"
    rounds = body["rounds"]
    assert len(rounds) == 3
    assert [r["round_number"] for r in rounds] == [1, 2, 3]
    # Every round captured the reasoning the policy returned
    for r in rounds:
        assert r["reasoning"]
        assert r["action"] in ("accept", "counter", "reject")
    # Final round should be an accept on this trajectory
    assert rounds[2]["action"] == "accept"
