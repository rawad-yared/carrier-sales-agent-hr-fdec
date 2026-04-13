from tests.conftest import API_KEY

AUTH = {"X-API-Key": API_KEY}


def test_search_loads_returns_available_loads(client):
    r = client.post("/api/search-loads", json={}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    # only 2 of 3 seeded loads are 'available' (L-9003 is 'booked')
    assert body["count"] == 2
    ids = [row["load_id"] for row in body["results"]]
    assert "L-9001" in ids
    assert "L-9002" in ids
    assert "L-9003" not in ids


def test_search_loads_filters_by_equipment(client):
    r = client.post("/api/search-loads", json={"equipment_type": "Reefer"}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["results"][0]["load_id"] == "L-9002"


def test_search_loads_fuzzy_origin_match(client):
    r = client.post("/api/search-loads", json={"origin": "Dallas"}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["results"][0]["origin"] == "Dallas, TX"


def test_search_loads_fuzzy_state_match(client):
    r = client.post("/api/search-loads", json={"destination": "GA"}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["results"][0]["destination"] == "Atlanta, GA"


def test_search_loads_respects_max_results(client):
    r = client.post("/api/search-loads", json={"max_results": 1}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_search_loads_requires_api_key(client):
    r = client.post("/api/search-loads", json={})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_search_loads_rejects_wrong_api_key(client):
    r = client.post("/api/search-loads", json={}, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
