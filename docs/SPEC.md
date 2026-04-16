# Product Spec — Inbound Carrier Sales Agent

## The problem

Freight brokers spend a large share of their day fielding inbound calls from carriers (truckers / trucking companies) who want to book loads. Each call follows roughly the same script: verify the carrier is legitimate, find a load that matches their equipment and lane, pitch it, negotiate the rate, and hand off to a human rep to close. The work is repetitive, high-volume, and the rate negotiation alone is a major margin lever.

## The solution

An AI voice agent, built on the HappyRobot platform, that answers inbound carrier calls and runs the full pre-close workflow autonomously. When a deal is struck, it transfers to a human sales rep. Every call is logged and surfaced in a dashboard for the broker to review.

## Users

- **Primary user (caller):** a carrier dispatcher or owner-operator looking to book a load.
- **Secondary user (operator):** the freight broker — uses the dashboard to monitor calls, audit the agent's decisions, and tune negotiation parameters.
- **Buyer (the pitch audience):** Carlos Becker at HappyRobot, evaluating this as a vendor PoC.

## Carrier call flow (the happy path)

1. Carrier dials in (web call trigger for this PoC).
2. Agent greets, asks for **MC number**.
3. Agent calls `/verify-carrier` → FMCSA lookup → confirms `allowedToOperate == Y`.
4. If not eligible: polite decline, classify outcome as `carrier_ineligible`, end call.
5. Agent asks what lane / equipment they're looking for.
6. Agent calls `/search-loads` with carrier's criteria → returns best match(es).
7. Agent pitches the load: origin, destination, pickup/delivery times, equipment, rate, key notes.
8. Agent asks if carrier is interested.
9. **Negotiation loop** (max 3 rounds):
   - Carrier accepts → go to step 10.
   - Carrier counters → agent calls `/evaluate-offer` → responds with accept / counter / reject per locked policy (see `NEGOTIATION.md`).
   - Carrier rejects outright → classify outcome as `carrier_declined`, end call.
10. On agreement: agent confirms terms, says *"Transferring you to a sales rep now…"* — mocked with *"Transfer was successful, you can wrap up the conversation."*
11. Post-call: HappyRobot extracts structured data, classifies outcome and sentiment, POSTs to `/log-call`.

## Functional requirements

| # | Requirement | Where it lives |
|---|---|---|
| F1 | Collect MC number from caller | HappyRobot agent |
| F2 | Verify eligibility via FMCSA | `/verify-carrier` |
| F3 | Search loads by carrier criteria | `/search-loads` |
| F4 | Pitch load details conversationally | HappyRobot agent |
| F5 | Negotiate, max 3 rounds, smart policy | `/evaluate-offer` |
| F6 | Mock transfer on agreement | HappyRobot agent |
| F7 | Extract offer data from call | HappyRobot post-call node |
| F8 | Classify call outcome | HappyRobot post-call node |
| F9 | Classify carrier sentiment | HappyRobot post-call node |
| F10 | Persist all of the above | `/log-call` |
| F11 | Display metrics dashboard (Ops + Exec tabs) | Streamlit |
| F12 | Call-flow Sankey + geographic lane map with supply-gap overlay | Streamlit (Exec tab) |
| F13 | Weekly Report tab — prose executive summary with auto-generated bullets | Streamlit (Report tab) |

## Non-functional requirements

- **Latency:** API endpoints respond in <500ms p95 (carrier is on the phone).
- **Security:** HTTPS only, API key on every endpoint, secrets in AWS Secrets Manager.
- **Reproducibility:** entire infra spun up via `terraform apply`. Local dev via `docker-compose up`.
- **Observability:** structured logs to CloudWatch, every API call logged with request ID.

## Outcome taxonomy (for F8)

Exactly one per call:
- `booked` — carrier and broker agreed on price, transfer initiated
- `carrier_declined` — carrier rejected the load or final counter
- `broker_declined` — agent rejected carrier's final offer (below floor)
- `no_match` — no suitable load found for carrier's criteria
- `carrier_ineligible` — failed FMCSA check
- `abandoned` — call dropped or carrier hung up mid-flow
- `error` — system error prevented completion

## Sentiment taxonomy (for F9)

- `positive` — engaged, cooperative, friendly
- `neutral` — transactional, no strong tone
- `negative` — frustrated, rude, or hostile

## Out of scope (be explicit, defend in pitch)

- Real phone number / PSTN (web call only, per challenge instructions)
- Actual call transfer to human (mocked)
- Multi-load pitching in one call (pitch best match; if rejected, optionally suggest one more — design choice, see `HAPPYROBOT.md`)
- CRM / TMS integration (would be phase 2)
- Carrier insurance verification beyond FMCSA `allowedToOperate`
- Multi-tenant / multi-broker support
- Auth/SSO for the dashboard (PoC = single shared login or IP allowlist)

## Acceptance criteria (the demo must show)

1. Cold call from web → agent greets and asks MC number
2. Eligible carrier sees a real FMCSA lookup happen
3. Ineligible MC number gets politely declined
4. Load pitch matches data in the DB
5. Negotiation runs at least 2 rounds, agent counters intelligently
6. Agreed price triggers the mock transfer message
7. Call appears in dashboard within 30 seconds of ending
8. Dashboard Ops tab shows the call's outcome + sentiment + transcript
9. Dashboard Exec tab shows aggregated metrics that change after the demo call
10. Everything served over HTTPS with API key auth on the backend
