# Inbound Carrier Sales — HappyRobot FDE Challenge

Proof of concept: an AI voice agent that answers inbound carrier calls for a freight brokerage, verifies the carrier, matches a load, negotiates the rate, and hands off to a human rep.

Built on the HappyRobot platform + a FastAPI backend + a Streamlit dashboard, deployed to AWS with Terraform.

## Status

🟡 In progress. See `docs/DELIVERABLES.md` for what's done.

## The deliverables

1. Email to Carlos Becker — `deliverables/email.md`
2. Build description for "Acme Logistics" — `deliverables/acme-logistics-proposal.md`
3. Deployed dashboard — `https://<custom-domain>/` (TBD)
4. This repo
5. HappyRobot workflow link — in `docs/HAPPYROBOT.md`
6. 5-min demo video — link in `deliverables/video.md`

## Local quickstart

```bash
cp .env.example .env
# fill in FMCSA_WEBKEY, API_KEY, DB_URL (defaults work for docker-compose)
docker-compose up --build
```

- API: http://localhost:8000 (docs at `/docs`)
- Dashboard: http://localhost:8501

## Deploy to AWS

See `docs/INFRA.md`. TL;DR:
```bash
cd infra
terraform init
terraform apply
```

## Project structure

```
carrier-sales-agent-hr-fdec/
├── README.md                 ← you are here
├── docs/                     ← specs and design docs
├── api/                      ← FastAPI backend
├── dashboard/                ← Streamlit dashboard
├── infra/                    ← Terraform
├── data/                     ← seed loads
├── deliverables/             ← email, proposal doc, video link
└── docker-compose.yml
```

## For reviewers

- Start with `docs/SPEC.md` for what this does
- Then `docs/ARCHITECTURE.md` for how
- `docs/NEGOTIATION.md` is the interesting piece of logic
- `docs/SECURITY.md` explains what's PoC-grade vs production-grade

## Tech

FastAPI · PostgreSQL · Streamlit · Docker · AWS (ECS Fargate, ALB, RDS, Secrets Manager, ACM, Route 53) · Terraform · HappyRobot
