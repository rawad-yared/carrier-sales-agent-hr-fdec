# HappyRobot workflow — setup guide

Everything you need to build the inbound carrier sales agent inside the HappyRobot platform. Our backend is live at `https://carrier-sales-demo.com/api/*`; this directory tells you how to point a HappyRobot workflow at it.

## What's in here

```
happyrobot/
├── README.md                     ← you are here
├── system-prompt.md              ← agent instructions (copy into the prompt node)
├── extraction-schema.json        ← post-call extraction schema
├── classification.md             ← outcome + sentiment rules
└── tools/
    ├── verify_carrier.json       ← FMCSA lookup
    ├── search_loads.json         ← load matching
    ├── evaluate_offer.json       ← 3-round negotiation
    └── log_call.json             ← post-call persist
```

Each tool JSON has everything you need to configure a webhook/tool node: URL, method, headers, request body template, parameters schema, response schema, example payloads, and error handling notes.

---

## Prerequisites

1. HappyRobot workspace with access to create agents and tools
2. Our backend's API key — retrieve it from AWS Secrets Manager:
   ```bash
   AWS_PROFILE=carrier-sales aws secretsmanager get-secret-value \
     --secret-id carrier-sales/api-key \
     --region us-east-1 \
     --query SecretString --output text
   ```
3. Confirm the backend is up:
   ```bash
   curl https://carrier-sales-demo.com/api/health
   # → {"status":"ok"}
   ```

---

## Setup, step by step

### 1. Store the API key as a workspace secret

In HappyRobot, create a workspace secret named `CARRIER_SALES_API_KEY` with the value from Secrets Manager. The tool JSONs reference it as `{{SECRETS.CARRIER_SALES_API_KEY}}`. **Never paste the key directly into tool configs** — it'll end up in version history and logs.

### 2. Register the four tools

For each file in `tools/`, create a new tool/function/webhook in the HappyRobot UI with these settings:

| Field | Value |
|---|---|
| Name | `name` from the JSON |
| Description | `description` (this is what the LLM sees to decide when to call) |
| HTTP method | `http.method` |
| URL | `http.url` (starts with `https://carrier-sales-demo.com/api/`) |
| Headers | `http.headers` — the `X-API-Key` maps to the workspace secret |
| Request body | `http.body` template |
| Parameters | `parameters` JSONSchema block — these become the LLM-facing function signature |

The `response_schema`, `errors`, and `examples` sections are reference material — HappyRobot may or may not let you import them, but keep them on hand while testing.

**Order to create them in:** verify_carrier → search_loads → evaluate_offer → log_call.

### 3. Create the agent

Create a new voice agent with:

- **Type:** inbound web call (no PSTN for this PoC)
- **System prompt:** contents of `system-prompt.md` (the fenced code block, not the surrounding explanatory text)
- **Tools:** all four you just created
- **Voice:** whatever sounds good — a neutral American voice works best for the freight brokerage context
- **LLM:** whichever model HappyRobot recommends for tool-calling workloads

### 4. Wire the post-call node

HappyRobot's post-call pipeline should run extraction, then classification, then the `log_call` tool as the final step:

1. **Extraction node** — use `extraction-schema.json`. Point it at the full transcript.
2. **Classification node** — two outputs: `outcome` and `sentiment`. Feed it the transcript and the extraction results. Use the rules in `classification.md`.
3. **log_call tool call** — wire extraction + classification outputs into the `log_call` body template as shown in `tools/log_call.json`.

### 5. Publish

Publish the workflow and grab the share link. Paste it into `docs/HAPPYROBOT.md` under "Link to deployed workflow" (or let the human maintainer do so) — this is deliverable #5.

---

## Dry-run checklist

Before recording the demo, verify each of these by making a real web call through the published workflow:

| # | Scenario | Expected flow | Verify on dashboard |
|---|---|---|---|
| 1 | **Eligible carrier, accepts listed rate** | Agent greets → MC 123456 → verify → lane/equipment → pitch → carrier says "sounds good" → transfer | Ops tab: new row, outcome=booked, 0 negotiation rounds |
| 2 | **Eligible carrier, 2-round agreement** | Same as above but carrier counters once, agent counters back, carrier accepts | Ops tab: outcome=booked, rounds=2, final_price < loadboard_rate |
| 3 | **Eligible carrier, round 3 reject** | Carrier lowballs 3 times below floor | Ops tab: outcome=broker_declined, rounds=3 |
| 4 | **Eligible carrier, walks away** | Counter-offer, carrier declines and hangs up | Ops tab: outcome=carrier_declined |
| 5 | **Ineligible carrier** | Agent verifies and FMCSA returns not-allowed-to-operate | Ops tab: outcome=carrier_ineligible, polite decline |
| 6 | **No matching load** | Carrier asks for a lane with no loads | Ops tab: outcome=no_match |
| 7 | **Invalid MC format** | Carrier says "MC ABCDEFG" | Agent asks to repeat; after one retry, ends as carrier_ineligible |

Each test call should show up in the Ops tab within ~15 seconds (dashboard cache TTL).

---

## Troubleshooting

**Tool call fails with 401 unauthorized** — the `X-API-Key` header isn't reaching the backend. Verify the workspace secret is set and the header template is correct.

**Tool call fails with 404 load_not_found on evaluate_offer** — the agent is passing the wrong `load_id`. Make sure it's using the exact value from `search_loads` results, not paraphrasing.

**Agent loses track of round_number** — HappyRobot may not have a durable conversation variable. Add this line to the system prompt: "Before calling evaluate_offer, state the round number to yourself: 'This is round N'. N is 1 the first time the carrier counters, 2 the second time, 3 the third."

**Post-call log_call fires before extraction finishes** — ensure the pipeline is sequential, not parallel. `log_call` must be the last node.

**Call doesn't appear on the dashboard** — check CloudWatch logs for the api service:
```bash
AWS_PROFILE=carrier-sales aws logs tail /ecs/carrier-sales-api --follow --region us-east-1
```
Look for a POST /api/log-call line. If you see 422, the outcome or sentiment enum is wrong. If you see 401, the API key is missing.

---

## Open questions

Things I flagged while drafting that you may want to validate inside the HappyRobot UI:

- [ ] Does HappyRobot expose the session/call ID as `{{session.id}}` or under a different variable name? Update all tool JSONs if different.
- [ ] How does HappyRobot handle numeric tool responses in speech? The `counter_price` from `evaluate_offer` needs to be spoken naturally — verify the agent says "twenty-three fifty", not "2350.00".
- [ ] Is there a native conversation-state variable for `round_number`, or must the agent track it in memory? Affects prompt reliability.
- [ ] What's the exact post-call webhook mechanism — a dedicated node, or a trigger off conversation-end?
- [ ] Does HappyRobot retry tool calls on transient 5xx automatically? If not, add retry logic in the node config for `verify_carrier` (occasional FMCSA 5xx is expected).
