# Inbound Carrier Sales

An AI voice agent that answers inbound carrier calls for a freight brokerage: verifies the carrier via FMCSA, searches matching loads, runs a bounded 3-round rate negotiation, and hands off to a human rep on agreement. Every call is logged and surfaced on a live operations dashboard.

**Live:** <https://carrier-sales-demo.com>

Built as a proof of concept for HappyRobot's FDE technical challenge.

---

## Architecture at a glance

```
Carrier (web call)
       │
       ▼
┌─────────────────────┐
│  HappyRobot agent   │  prompt · voice · tool orchestration · post-call extraction
└──────────┬──────────┘
           │ HTTPS + X-API-Key
           ▼
┌─────────────────────────────────┐
│  AWS ALB (ACM cert, path rules) │
└──┬────────────────────────────┬─┘
   │ /api/*                     │ /*
   ▼                            ▼
┌────────────────┐      ┌─────────────────┐
│ FastAPI  (ECS) │      │ Streamlit (ECS) │
│ 6 endpoints    │      │ Ops + Exec tabs │
└──────┬─────────┘      └────────┬────────┘
       │                         │
       └──────────┬──────────────┘
                  ▼
           ┌──────────────┐
           │ RDS Postgres │
           └──────────────┘
```

| Layer | Stack |
|---|---|
| Voice agent | HappyRobot (prompt, LLM, tool orchestration, post-call nodes) |
| Backend | FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · psycopg3 · httpx |
| Dashboard | Streamlit · Pandas · Plotly |
| Data | PostgreSQL 16 |
| Infra | AWS ECS Fargate · ALB · RDS · ACM · Route 53 · Secrets Manager · CloudWatch · ECR |
| IaC | Terraform (S3 + DynamoDB state) |

See `docs/ARCHITECTURE.md` for the full system diagram and component breakdown.

---

## API

Six endpoints, path-prefixed with `/api`. All require `X-API-Key` except `/health`.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe (no auth) |
| `POST /api/verify-carrier` | FMCSA lookup by MC number; returns eligible + carrier metadata |
| `POST /api/search-loads` | Fuzzy origin/destination match, exact equipment match, pickup date filter |
| `POST /api/evaluate-offer` | Apply the locked 3-round negotiation policy; pulls prior-round history by `session_id` |
| `POST /api/log-call` | Persist a completed call with outcome, sentiment, negotiation rounds, transcript |
| `GET /api/calls` | Paginated read with outcome + since filters |
| `GET /api/metrics/summary` | Aggregated KPIs (acceptance rate, avg margin vs loadboard, booked revenue) |

Full contract in `docs/API.md`. OpenAPI schema served at `/docs` on the deployed API.

---

## Negotiation policy — the interesting bit

Stateless 3-round "smart" policy that balances broker margin against time-to-close:

- **Round 1:** accept if offer ≥ `target` (0.98 × loadboard); else counter at midpoint of offer and loadboard
- **Round 2:** accept if ≥ target; else concede half the remaining gap from our round-1 counter
- **Round 3:** accept if ≥ `floor` (0.92 × loadboard); else reject (final)

Below-floor offers at R1/R2 get a signal counter at target or floor × 1.01 respectively. Every decision includes a human-readable reasoning string. All four worked examples from `docs/NEGOTIATION.md` are covered by unit tests (16 test cases).

See `docs/NEGOTIATION.md` for the exact rules and `api/app/services/negotiation.py` for the pure implementation.

---

## Dashboard

Two tabs, both read from `/api/calls` and `/api/metrics/summary` with Streamlit's `@st.cache_data` for polling.

**Ops** — live broker console: calls today / active now / booked today / acceptance today KPIs, call feed table with color-coded outcome badges, drill-down panel showing transcript + HappyRobot-extracted data.

**Exec** — aggregate view: total calls / booked / acceptance rate / avg margin vs loadboard / revenue KPIs, plus 6 Plotly charts (volume over time stacked by outcome, outcome donut, sentiment donut, avg rounds by outcome, delta-from-loadboard histogram, top lanes booked).

Spec in `docs/DASHBOARD.md`.

---

## Local development

```bash
cp .env.example .env
# fill in FMCSA_WEBKEY; API_KEY/DASHBOARD_API_KEY can be any shared string
docker compose up --build
```

- API: <http://localhost:8000> (health at `/health`, OpenAPI docs at `/docs`)
- Dashboard: <http://localhost:8501>

The api container runs `alembic upgrade head` and seeds `data/loads.json` on start. For demo data in Ops/Exec tabs:

```bash
python scripts/seed_synthetic_calls.py
```

### Tests

```bash
cd api
python -m pytest tests/
```

**73 tests** covering negotiation policy (all 4 docs/NEGOTIATION.md worked examples verbatim), endpoint happy paths, 401 auth failures, rate limiting, FMCSA mocking, metrics aggregation, and defensive coercion for LLM-originated tool-call payloads (number-to-string, flexible datetime, transcript array flattening).

---

## AWS deploy

Terraform provisions the full stack (VPC, NAT, ALB, ACM cert, RDS, ECS, ECR, Secrets Manager, CloudWatch, Cloud Map service discovery).

```bash
AWS_PROFILE=carrier-sales scripts/bootstrap-tf-state.sh  # once per account
cd infra
export AWS_PROFILE=carrier-sales
export TF_VAR_fmcsa_webkey="..."
terraform init
terraform apply
cd ..
AWS_PROFILE=carrier-sales scripts/build-and-push.sh
```

Full runbook, cost breakdown, and teardown instructions in `infra/README.md`.

**Estimated cost:** ~$78/mo (biggest line item is the NAT gateway at ~$32/mo).

---

## Project layout

```
carrier-sales-agent-hr-fdec/
├── README.md                 ← you are here
├── docs/                     ← specs and design docs (human-authored)
├── api/                      ← FastAPI backend + Alembic + tests
├── dashboard/                ← Streamlit Ops + Exec tabs
├── infra/                    ← Terraform modules
├── data/                     ← seed loads (loads.json)
├── happyrobot/               ← HappyRobot workflow artifacts (tool defs, prompts)
├── deliverables/             ← email, Acme proposal, video link
├── scripts/                  ← bootstrap, build-and-push, synthetic seeder
└── docker-compose.yml
```

---

## For reviewers

Recommended reading order:

1. **`docs/SPEC.md`** — what this is, the call flow, the acceptance criteria
2. **`docs/ARCHITECTURE.md`** — how the pieces fit
3. **`docs/NEGOTIATION.md`** — the core business logic
4. **`api/app/services/negotiation.py`** — 150 lines that implement it
5. **`api/tests/test_negotiation.py`** — proof that it matches the spec
6. **`docs/SECURITY.md`** — what's PoC-grade vs production-grade

The `docs/` directory is the source of truth for what the system should do; the `api/`, `dashboard/`, and `infra/` directories are how it actually does it.
