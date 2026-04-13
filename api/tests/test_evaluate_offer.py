from tests.conftest import API_KEY

AUTH = {"X-API-Key": API_KEY}


def _body(load_id="L-9001", offer=2300.00, round_number=1, session_id="sess-test-1"):
    return {
        "load_id": load_id,
        "carrier_offer": offer,
        "round_number": round_number,
        "session_id": session_id,
    }


def test_evaluate_offer_happy_path_counter(client):
    # L-9001 has loadboard $2400.00. Floor 0.92 → $2208, Target 0.98 → $2352.
    # Offer $2300 is above floor, below target → counter at midpoint
    # (2300 + 2400) / 2 = 2350
    r = client.post("/evaluate-offer", json=_body(offer=2300.00), headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "counter"
    assert float(body["counter_price"]) == 2350.00
    assert body["final"] is False


def test_evaluate_offer_instant_accept_at_target(client):
    # L-9001 $2400 * 0.98 = $2352. Offer $2360 → instant accept.
    r = client.post("/evaluate-offer", json=_body(offer=2360.00), headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "accept"
    assert body["counter_price"] is None
    assert body["final"] is True


def test_evaluate_offer_round3_below_floor_rejects(client):
    r = client.post("/evaluate-offer", json=_body(offer=2000.00, round_number=3), headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "reject"
    assert body["final"] is True


def test_evaluate_offer_uses_prior_round_counter_from_db(client):
    # R1: offer 2200 (below floor 2208) → counter at target 2352
    r1 = client.post(
        "/evaluate-offer",
        json=_body(offer=2200.00, round_number=1, session_id="sess-chain"),
        headers=AUTH,
    )
    assert r1.status_code == 200
    assert r1.json()["action"] == "counter"

    # R2: offer 2300 (above floor, below target) → concede half gap from 2352
    # new = 2300 + (2352 - 2300) * 0.5 = 2326
    r2 = client.post(
        "/evaluate-offer",
        json=_body(offer=2300.00, round_number=2, session_id="sess-chain"),
        headers=AUTH,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["action"] == "counter"
    assert float(body["counter_price"]) == 2326.00


def test_evaluate_offer_invalid_round_returns_400(client):
    r = client.post("/evaluate-offer", json=_body(round_number=4), headers=AUTH)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_round"


def test_evaluate_offer_zero_offer_returns_400(client):
    r = client.post("/evaluate-offer", json=_body(offer=0), headers=AUTH)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_offer"


def test_evaluate_offer_negative_offer_returns_400(client):
    r = client.post("/evaluate-offer", json=_body(offer=-100), headers=AUTH)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_offer"


def test_evaluate_offer_nonexistent_load_returns_404(client):
    r = client.post("/evaluate-offer", json=_body(load_id="L-9999"), headers=AUTH)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "load_not_found"


def test_evaluate_offer_requires_api_key(client):
    r = client.post("/evaluate-offer", json=_body())
    assert r.status_code == 401
