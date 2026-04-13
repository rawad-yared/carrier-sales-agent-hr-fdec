# Post-call classification

After extraction, the HappyRobot classification node picks exactly one value for each of two dimensions. Both feed the `/api/log-call` request body.

## Outcome (pick one)

These match the backend's enum exactly — any other value will be rejected with a 422.

| Outcome | When to pick it |
|---|---|
| `booked` | Carrier and broker agreed on a price. Agent said the mock transfer line. There's a `final_agreed_price`. |
| `carrier_declined` | Agent offered a counter (or the listed rate) and the carrier walked away. The carrier, not the broker, said no. |
| `broker_declined` | Round 3 ended with `action: reject` — the broker (via `evaluate_offer`) refused to go lower. |
| `no_match` | `search_loads` returned zero results for the carrier's lane/equipment. Negotiation never started. |
| `carrier_ineligible` | `verify_carrier` returned `eligible: false`, OR the MC format was invalid even after one retry. |
| `abandoned` | Carrier hung up mid-flow before a clear outcome (no_match, eligible check, etc). Use this sparingly — if the call has a clear reason, use that instead. |
| `error` | A system error prevented the call from completing — FMCSA down persistently, tool calls all failing, agent got confused and dropped the call. Last resort. |

**Decision order:** work from most-specific to least-specific. If the call matches multiple (e.g. abandoned AND carrier_ineligible), pick the one further left in the flow. Eligible check happens first, so `carrier_ineligible` wins over `abandoned`.

## Sentiment (pick one)

Assess the carrier's tone across the call, not just the last message.

| Sentiment | Signals |
|---|---|
| `positive` | Friendly, engaged, cooperative. Says "great", "sounds good", thanks the agent. Even if they didn't book, they were pleasant. |
| `neutral` | Transactional. Short answers, no strong affect either way. Most calls default here. |
| `negative` | Frustrated, rude, hostile, dismissive. Sighs, complains, pushes back aggressively on price, hangs up abruptly, uses strong language. |

**If in doubt → neutral.** Don't over-classify as negative — a carrier walking away after a tough negotiation isn't necessarily negative; it's just business.

## Combined examples

| Situation | outcome | sentiment |
|---|---|---|
| Carrier books at listed rate, friendly | `booked` | `positive` |
| Carrier books after 3 rounds, transactional | `booked` | `neutral` |
| Carrier counters twice, walks away politely | `carrier_declined` | `neutral` |
| Carrier counters, lowballs, swears at agent when rejected | `broker_declined` | `negative` |
| No loads on their lane, carrier says "OK thanks" and hangs up | `no_match` | `neutral` |
| Carrier ineligible, gets frustrated | `carrier_ineligible` | `negative` |
| Call drops before MC given | `abandoned` | `neutral` |
