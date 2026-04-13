from unittest.mock import MagicMock

import httpx
import pytest

from app.services import fmcsa
from tests.conftest import API_KEY

AUTH = {"X-API-Key": API_KEY}


def _ok_response(carrier: dict) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = 200
    r.json.return_value = {"content": [{"carrier": carrier}]}
    return r


def _empty_response() -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = 200
    r.json.return_value = {"content": []}
    return r


def _error_response(code: int = 500) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = code
    r.text = "upstream error"
    r.json.return_value = {}
    return r


def test_verify_carrier_eligible(client, monkeypatch):
    monkeypatch.setattr(
        fmcsa.httpx,
        "get",
        lambda *a, **kw: _ok_response(
            {
                "legalName": "ACME TRUCKING LLC",
                "dotNumber": 7654321,
                "allowedToOperate": "Y",
                "statusCode": "ACTIVE",
            }
        ),
    )
    r = client.post("/verify-carrier", json={"mc_number": "123456"}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["eligible"] is True
    assert body["mc_number"] == "123456"
    assert body["carrier_name"] == "ACME TRUCKING LLC"
    assert body["dot_number"] == "7654321"
    assert body["allowed_to_operate"] == "Y"
    assert body["raw_fmcsa_status"] == "ACTIVE"
    assert body["reason"] is None


def test_verify_carrier_ineligible(client, monkeypatch):
    monkeypatch.setattr(
        fmcsa.httpx,
        "get",
        lambda *a, **kw: _ok_response(
            {
                "legalName": "OLD TRUCKING",
                "dotNumber": 1111,
                "allowedToOperate": "N",
                "statusCode": "INACTIVE",
            }
        ),
    )
    r = client.post("/verify-carrier", json={"mc_number": "999999"}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["eligible"] is False
    assert body["reason"] == "not_allowed_to_operate"


def test_verify_carrier_not_found_returns_404(client, monkeypatch):
    monkeypatch.setattr(fmcsa.httpx, "get", lambda *a, **kw: _empty_response())
    r = client.post("/verify-carrier", json={"mc_number": "123456"}, headers=AUTH)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "carrier_not_found"


def test_verify_carrier_upstream_500_returns_502(client, monkeypatch):
    monkeypatch.setattr(fmcsa.httpx, "get", lambda *a, **kw: _error_response(500))
    r = client.post("/verify-carrier", json={"mc_number": "123456"}, headers=AUTH)
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "fmcsa_unavailable"


def test_verify_carrier_network_error_returns_502(client, monkeypatch):
    def _raise(*a, **kw):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(fmcsa.httpx, "get", _raise)
    r = client.post("/verify-carrier", json={"mc_number": "123456"}, headers=AUTH)
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "fmcsa_unavailable"


@pytest.mark.parametrize("bad", ["", "abc", "123456789", "12-34", "mc123"])
def test_verify_carrier_invalid_mc_format_returns_400(client, bad):
    r = client.post("/verify-carrier", json={"mc_number": bad}, headers=AUTH)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_mc_number"


def test_verify_carrier_requires_api_key(client):
    r = client.post("/verify-carrier", json={"mc_number": "123456"})
    assert r.status_code == 401
