# HappyRobot Workflow

> **Status: skeleton, waiting on platform access.** Fill in after user signs up and explores the UI. Structure below is based on the challenge spec.

## Workflow overview

A single inbound voice agent triggered by a **web call**. The agent:
1. Greets the caller
2. Collects MC number
3. Calls our `/verify-carrier` tool
4. Branches: eligible → continue; ineligible → polite decline + end
5. Asks for lane/equipment preference
6. Calls `/search-loads`
7. Branches: match found → pitch; no match → apologize + end
8. Pitches load details
9. Asks if carrier accepts
10. On counter: calls `/evaluate-offer`, loops up to 3 rounds
11. On agreement: mock transfer message
12. Post-call extraction + classification node
13. POSTs result to `/log-call`

## Tools to register in HappyRobot

Each tool = a call to our FastAPI backend. All include `X-API-Key` header.

| Tool name | Method | Path | Purpose |
|---|---|---|---|
| `verify_carrier` | POST | `/verify-carrier` | FMCSA check |
| `search_loads` | POST | `/search-loads` | Find load matches |
| `evaluate_offer` | POST | `/evaluate-offer` | Negotiation decision |
| `log_call` | POST | `/log-call` | Persist outcome (post-call) |

Tool schemas: mirror `docs/API.md` request/response bodies.

## Agent prompt (draft)

```
You are an inbound sales agent for a freight brokerage. A carrier is calling to book a load.

Your job:
1. Greet them warmly and ask for their MC number.
2. Use the verify_carrier tool to check eligibility. If not eligible, politely explain we can't work with them today and end the call.
3. Ask what lane they're looking for and what equipment they have.
4. Use search_loads to find a match. If nothing matches, apologize and end politely.
5. Pitch the load: origin, destination, pickup time, equipment needed, rate, and any important notes.
6. Ask if they're interested at the listed rate.
7. If they counter, use evaluate_offer with the current round number. Relay the decision conversationally:
   - Accept → "Great, we have a deal at $X. Let me transfer you to a rep."
   - Counter → "I can't quite do that, but I can meet you at $X. Does that work?"
   - Reject (round 3 final) → "Unfortunately we can't go that low. Thanks for calling."
8. Track round numbers yourself (1, 2, 3). Max 3 rounds.
9. On agreement, say: "Transferring you now..." then say "Transfer was successful, you can wrap up the conversation."

Always be professional, concise, and respectful of the carrier's time. Don't invent load details — only use what search_loads returned.
```

## Post-call extraction schema

HappyRobot's post-call node should extract:

```json
{
  "carrier_equipment": "string (e.g. 'Dry Van')",
  "carrier_current_location": "string or null",
  "notes_from_carrier": "string — anything the carrier said that's not standard",
  "counter_offers_made": ["array of numbers"],
  "final_agreed_price": "number or null"
}
```

## Classification

**Outcome** — pick one:
- `booked`, `carrier_declined`, `broker_declined`, `no_match`, `carrier_ineligible`, `abandoned`, `error`

**Sentiment** — pick one:
- `positive`, `neutral`, `negative`

Both fed into the `/log-call` body.

## Open questions (once we have platform access)

- [ ] Does HappyRobot expose a reliable `session_id` we can pass to our endpoints?
- [ ] Can tool calls be retried on transient failure?
- [ ] How does HappyRobot handle our `counter_price` numeric response — can the agent reliably speak a USD figure?
- [ ] Is there a native "variable" concept for round_number, or do we manage it in conversation state?
- [ ] What's the exact post-call webhook mechanism for `/log-call`?

## Link to deployed workflow

TBD — paste HappyRobot platform URL here once built.
