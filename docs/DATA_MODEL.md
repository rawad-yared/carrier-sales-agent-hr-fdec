# Data Model

Postgres 15+. All tables use `id` as primary key. Timestamps are `TIMESTAMPTZ`, all UTC.

## `loads`

The load board — populated from seed data (or HappyRobot export, TBD).

| Column | Type | Notes |
|---|---|---|
| `load_id` | `TEXT PRIMARY KEY` | e.g. `L-1042`. From source data, not auto-generated. |
| `origin` | `TEXT NOT NULL` | "Dallas, TX" |
| `destination` | `TEXT NOT NULL` | "Atlanta, GA" |
| `pickup_datetime` | `TIMESTAMPTZ NOT NULL` | |
| `delivery_datetime` | `TIMESTAMPTZ NOT NULL` | |
| `equipment_type` | `TEXT NOT NULL` | "Dry Van", "Reefer", "Flatbed", etc. |
| `loadboard_rate` | `NUMERIC(10,2) NOT NULL` | USD |
| `notes` | `TEXT` | |
| `weight` | `INTEGER` | lbs |
| `commodity_type` | `TEXT` | |
| `num_of_pieces` | `INTEGER` | |
| `miles` | `INTEGER` | |
| `dimensions` | `TEXT` | |
| `status` | `TEXT NOT NULL DEFAULT 'available'` | `available`, `booked`, `expired` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |

Indexes: `(equipment_type)`, `(pickup_datetime)`, `(origin)`, `(destination)`, `(status)`.

## `carriers`

Cached FMCSA lookups. Optional optimization — start without, add if rate limits hurt.

| Column | Type | Notes |
|---|---|---|
| `mc_number` | `TEXT PRIMARY KEY` | |
| `carrier_name` | `TEXT` | |
| `dot_number` | `TEXT` | |
| `allowed_to_operate` | `TEXT` | `Y` / `N` |
| `raw_fmcsa_response` | `JSONB` | full payload for audit |
| `last_checked_at` | `TIMESTAMPTZ NOT NULL` | |

## `calls`

One row per completed call. Written by `/log-call`.

| Column | Type | Notes |
|---|---|---|
| `call_id` | `TEXT PRIMARY KEY` | `c-<uuid>` generated on insert |
| `session_id` | `TEXT UNIQUE NOT NULL` | HappyRobot session ID |
| `mc_number` | `TEXT` | nullable — ineligible calls may have invalid MC |
| `carrier_name` | `TEXT` | |
| `load_id` | `TEXT REFERENCES loads(load_id)` | nullable — no_match calls have none |
| `outcome` | `TEXT NOT NULL` | see outcome taxonomy |
| `sentiment` | `TEXT NOT NULL` | `positive` / `neutral` / `negative` |
| `final_price` | `NUMERIC(10,2)` | nullable — only if booked |
| `negotiation_rounds` | `INTEGER NOT NULL DEFAULT 0` | |
| `started_at` | `TIMESTAMPTZ NOT NULL` | |
| `ended_at` | `TIMESTAMPTZ NOT NULL` | |
| `duration_seconds` | `INTEGER GENERATED ALWAYS AS (EXTRACT(EPOCH FROM ended_at - started_at)::INT) STORED` | |
| `transcript` | `TEXT` | full conversation |
| `extracted` | `JSONB` | HappyRobot-extracted structured data |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |

Indexes: `(outcome)`, `(started_at DESC)`, `(sentiment)`, `(load_id)`.

Constraint: `outcome IN ('booked', 'carrier_declined', 'broker_declined', 'no_match', 'carrier_ineligible', 'abandoned', 'error')`.
Constraint: `sentiment IN ('positive', 'neutral', 'negative')`.

## `negotiations`

One row per `/evaluate-offer` call. Ties back to a `calls` row via `session_id`.

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGSERIAL PRIMARY KEY` | |
| `session_id` | `TEXT NOT NULL` | joins to `calls.session_id` |
| `load_id` | `TEXT NOT NULL REFERENCES loads(load_id)` | |
| `round_number` | `INTEGER NOT NULL` | 1, 2, 3 |
| `carrier_offer` | `NUMERIC(10,2) NOT NULL` | |
| `action` | `TEXT NOT NULL` | `accept` / `counter` / `reject` |
| `counter_price` | `NUMERIC(10,2)` | nullable |
| `reasoning` | `TEXT` | |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |

Index: `(session_id)`.

## Seed data

`data/loads.json` — ~25 synthetic loads covering:
- 4+ equipment types (Dry Van, Reefer, Flatbed, Power Only)
- Major lanes (TX↔GA, CA↔AZ, IL↔NY, FL intra-state, etc.)
- Rate range $800–$4,500
- Pickup dates spread over next 14 days
- Variety of weights, commodities, notes

Loader: `api/seed.py` reads the JSON and upserts into `loads`. Idempotent — safe to run multiple times.

## Migrations

Use Alembic. Each schema change is a migration file. Initial migration creates all four tables. Terraform does not touch schema — the API container runs `alembic upgrade head` on startup.
