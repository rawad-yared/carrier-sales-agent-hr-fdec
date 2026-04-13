# API Contracts

Base URL (prod): `https://<custom-domain>/api`
Base URL (local): `http://localhost:8000`

All endpoints require `X-API-Key: <key>` header. Missing or invalid → `401`.
All responses are JSON. Errors follow `{error: {code, message, request_id}}`.

---

## `POST /verify-carrier`

Verify a carrier by MC number via FMCSA.

**Request:**
```json
{ "mc_number": "123456" }
```

**Response 200:**
```json
{
  "eligible": true,
  "mc_number": "123456",
  "carrier_name": "ACME TRUCKING LLC",
  "dot_number": "7654321",
  "allowed_to_operate": "Y",
  "raw_fmcsa_status": "ACTIVE"
}
```

**Response 200 (ineligible):**
```json
{
  "eligible": false,
  "mc_number": "123456",
  "reason": "not_allowed_to_operate",
  "raw_fmcsa_status": "INACTIVE"
}
```

**Errors:**
- `400 invalid_mc_number` — not a valid format
- `404 carrier_not_found` — FMCSA returned no record
- `502 fmcsa_unavailable` — upstream error, safe to retry

---

## `POST /search-loads`

Find loads matching carrier criteria.

**Request:**
```json
{
  "origin": "Dallas, TX",
  "destination": "Atlanta, GA",
  "equipment_type": "Dry Van",
  "pickup_date": "2026-04-15",
  "max_results": 3
}
```

All fields optional. Empty request returns top-N available loads sorted by pickup date. Matching uses fuzzy string match on origin/destination (city or state), exact match on equipment.

**Response 200:**
```json
{
  "results": [
    {
      "load_id": "L-1042",
      "origin": "Dallas, TX",
      "destination": "Atlanta, GA",
      "pickup_datetime": "2026-04-15T08:00:00Z",
      "delivery_datetime": "2026-04-16T18:00:00Z",
      "equipment_type": "Dry Van",
      "loadboard_rate": 2400.00,
      "notes": "No-touch freight, drop-and-hook at destination",
      "weight": 18500,
      "commodity_type": "Packaged consumer goods",
      "num_of_pieces": 24,
      "miles": 781,
      "dimensions": "48ft trailer"
    }
  ],
  "count": 1
}
```

---

## `POST /evaluate-offer`

Apply negotiation policy to a carrier counter-offer. See `NEGOTIATION.md` for the logic.

**Request:**
```json
{
  "load_id": "L-1042",
  "carrier_offer": 2600.00,
  "round_number": 1,
  "session_id": "call-uuid-here"
}
```

**Response 200:**
```json
{
  "action": "counter",
  "counter_price": 2500.00,
  "round_number": 1,
  "reasoning": "Offer above floor but below target; splitting the difference",
  "final": false
}
```

`action` is one of: `accept`, `counter`, `reject`.
`final: true` means this is round 3 and no more negotiation is allowed.

**Errors:**
- `400 invalid_round` — round not in {1, 2, 3}
- `404 load_not_found`

---

## `POST /log-call`

Persist a completed call. Called once, by HappyRobot post-call node.

**Request:**
```json
{
  "session_id": "call-uuid",
  "mc_number": "123456",
  "carrier_name": "ACME TRUCKING LLC",
  "load_id": "L-1042",
  "outcome": "booked",
  "sentiment": "positive",
  "final_price": 2500.00,
  "negotiation_rounds": 2,
  "started_at": "2026-04-13T14:22:01Z",
  "ended_at": "2026-04-13T14:26:44Z",
  "transcript": "...",
  "extracted": {
    "carrier_equipment": "Dry Van",
    "carrier_current_location": "Fort Worth, TX",
    "notes_from_carrier": "Can do it tomorrow if picked up by noon"
  }
}
```

**Response 201:**
```json
{ "call_id": "c-0001", "status": "logged" }
```

`outcome` must be one of the values in `SPEC.md` outcome taxonomy.
`sentiment` must be one of: `positive`, `neutral`, `negative`.

---

## `GET /calls`

Read calls (dashboard). Supports filters and pagination.

**Query params:**
- `limit` (default 50, max 500)
- `offset` (default 0)
- `outcome` (optional, filter)
- `since` (optional, ISO datetime)

**Response 200:**
```json
{
  "results": [ /* array of call objects as in /log-call */ ],
  "total": 142,
  "limit": 50,
  "offset": 0
}
```

---

## `GET /metrics/summary`

Aggregated metrics for the exec dashboard tab.

**Query params:**
- `since` (optional, default = 30 days ago)

**Response 200:**
```json
{
  "total_calls": 142,
  "outcomes": {
    "booked": 47,
    "carrier_declined": 31,
    "broker_declined": 12,
    "no_match": 28,
    "carrier_ineligible": 18,
    "abandoned": 5,
    "error": 1
  },
  "sentiment": { "positive": 72, "neutral": 55, "negative": 15 },
  "acceptance_rate": 0.33,
  "avg_negotiation_rounds": 1.8,
  "avg_delta_from_loadboard": -0.04,
  "total_booked_revenue": 112400.00
}
```

---

## `GET /health`

Unauthenticated. Returns `{status: "ok"}`. Used by ALB health checks.

---

## Auth details

- Header: `X-API-Key: <key>`
- Key lives in AWS Secrets Manager in prod, `.env` locally
- Single shared key for the PoC (HappyRobot uses one, dashboard uses one, same key is fine)
- Rate limit: 60 req/min per IP (in-memory for PoC, not distributed)

## Versioning

No versioning in URLs for the PoC. If we break a contract after HappyRobot workflow is built, we version (`/api/v2/...`).
