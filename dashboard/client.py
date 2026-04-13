import os

import httpx


class ApiClient:
    def __init__(self) -> None:
        self.base_url = os.environ.get("API_BASE_URL", "http://api:8000").rstrip("/")
        self.api_key = os.environ.get("DASHBOARD_API_KEY", "")
        self._client = httpx.Client(timeout=10.0)

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    def health(self) -> dict:
        r = self._client.get(f"{self.base_url}/health")
        r.raise_for_status()
        return r.json()

    def search_loads(self, body: dict | None = None) -> dict:
        r = self._client.post(
            f"{self.base_url}/search-loads",
            json=body or {},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()
