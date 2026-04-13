# Architecture

## System diagram

```
                    ┌───────────────────────┐
                    │  Carrier (web call)   │
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌───────────────────────┐
                    │  HappyRobot platform  │
                    │  - Voice agent        │
                    │  - Tool calls         │
                    │  - Post-call extract  │
                    └──────────┬────────────┘
                               │ HTTPS + X-API-Key
                               ▼
              ┌────────────────────────────────────┐
              │  AWS ALB (custom domain, ACM cert) │
              └──────┬──────────────────┬──────────┘
                     │                  │
            /api/*   │                  │  / (everything else)
                     ▼                  ▼
        ┌────────────────────┐  ┌────────────────────┐
        │ FastAPI (ECS task) │  │ Streamlit (ECS)    │
        │ - /verify-carrier  │  │ - Ops tab          │
        │ - /search-loads    │  │ - Exec tab         │
        │ - /evaluate-offer  │  │                    │
        │ - /log-call        │  │                    │
        │ - /calls (read)    │  │                    │
        └─────────┬──────────┘  └─────────┬──────────┘
                  │                       │
                  └──────────┬────────────┘
                             ▼
                  ┌──────────────────────┐
                  │  RDS Postgres (db)   │
                  └──────────────────────┘

                  ┌──────────────────────┐
                  │ AWS Secrets Manager  │  ← FMCSA key, API keys, DB creds
                  └──────────────────────┘

                  ┌──────────────────────┐
                  │     CloudWatch       │  ← logs from both ECS services
                  └──────────────────────┘
```

## Components

### HappyRobot agent
The conversational layer. Owns greeting, asking questions, deciding which tool to call, and post-call extraction/classification. We provide it with our API endpoints as tools and define its prompt + flow in the platform UI. See `HAPPYROBOT.md`.

### FastAPI backend
The brains. Stateless REST API. Owns FMCSA integration, load search, negotiation policy, and call logging. One container, one ECS service. See `API.md` and `NEGOTIATION.md`.

### Streamlit dashboard
Read-only UI for the broker. Two tabs:
- **Ops** — live call feed, recent outcomes, drill into a single call
- **Exec** — aggregate trends, acceptance rate, sentiment, margin metrics

Reads from the FastAPI backend's `/calls` endpoint (or queries the DB directly — TBD, see open question below). One container, one ECS service. See `DASHBOARD.md`.

### Postgres (RDS)
Single source of truth. Tables: `loads`, `carriers`, `calls`, `negotiations`. See `DATA_MODEL.md`.

### AWS infrastructure
- **ECS Fargate** — runs both containers serverlessly
- **ALB** — single load balancer, path-based routing
- **ACM** — TLS cert for the custom domain
- **Route 53** — DNS for the custom domain
- **RDS Postgres** — `db.t4g.micro`, single AZ (PoC, not prod)
- **Secrets Manager** — all secrets, mounted into ECS tasks via task role
- **CloudWatch** — logs and basic metrics
- **ECR** — container registry for our two images

All defined in Terraform. See `INFRA.md`.

## Tech choices and why

| Choice | Why |
|---|---|
| FastAPI | Fast, typed, auto-generates OpenAPI for HappyRobot tool definitions |
| Postgres on RDS | Real DB, supports JSON columns for transcripts, broker IT teams trust it |
| Streamlit | Fastest path to a respectable dashboard; same language as backend |
| ECS Fargate | No EC2 management, scales to zero-ish cost at idle, simple Terraform |
| ALB + path routing | One cert, one DNS record, two services behind it |
| Terraform | Industry standard, reproducible, what enterprise IT expects |
| AWS Secrets Manager | Native ECS integration via task role, no secrets in env files in prod |

## Data flow: a single call

1. Carrier connects → HappyRobot agent picks up
2. Agent asks for MC number → carrier says "MC 123456"
3. Agent calls `POST /verify-carrier` with `{mc_number: "123456"}`
4. Backend hits FMCSA, returns `{eligible: true, carrier_name: "...", ...}`
5. Agent asks for lane/equipment preferences
6. Agent calls `POST /search-loads` with criteria → returns load(s)
7. Agent pitches, asks for response
8. Carrier counters at $X → agent calls `POST /evaluate-offer` with `{load_id, carrier_offer, round_number}`
9. Backend applies negotiation policy → returns `{action: "counter", price: Y, reasoning: "..."}`
10. Repeat 8–9 up to 3 rounds
11. On agreement, agent says transfer message
12. HappyRobot post-call node extracts data + classifies → POSTs to `/log-call`
13. Dashboard polls `/calls` every N seconds → call appears

## Open architectural questions

- **Dashboard data access:** does Streamlit hit the FastAPI `/calls` endpoint, or query Postgres directly with a read-only user? Default = hit the API (cleaner separation, but adds latency). Revisit if dashboard feels sluggish.
- **Single ALB vs. two:** could use one ALB with path routing, or two ALBs (one per service). Default = one. Cheaper and simpler.
- **Caching:** FMCSA responses could be cached for ~24h to reduce calls. Default = no cache for PoC, add if rate limits bite.
