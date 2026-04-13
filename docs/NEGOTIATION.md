# Negotiation Policy

The locked 3-round negotiation policy. This is the feature that differentiates the demo; do not change without user approval.

## Parameters (configurable via env vars)

| Param | Default | Meaning |
|---|---|---|
| `FLOOR_PCT` | `0.92` | Broker's hard floor — never accept below this fraction of loadboard rate |
| `TARGET_PCT` | `0.98` | Target — any offer at or above this is an instant accept |
| `STRATEGY` | `smart` | `simple` or `smart`. See below. |

All rates below are computed from the load's `loadboard_rate`:
- `floor = loadboard_rate × FLOOR_PCT`
- `target = loadboard_rate × TARGET_PCT`

## Smart strategy (default)

**Round 1:**
- If `carrier_offer ≥ target` → **accept**
- If `carrier_offer ≥ floor` → **counter** at midpoint: `(carrier_offer + loadboard_rate) / 2`
- If `carrier_offer < floor` → **counter** at `loadboard_rate × TARGET_PCT` (signal we have room but not much)

**Round 2:**
- If `carrier_offer ≥ target` → **accept**
- If `carrier_offer ≥ floor` → **counter**, concede 50% of remaining gap:
  `new_counter = carrier_offer + (our_last_counter - carrier_offer) × 0.5`
- If `carrier_offer < floor` → **counter** at `floor × 1.01` (one last signal)

**Round 3 (final):**
- If `carrier_offer ≥ floor` → **accept** (take the deal)
- If `carrier_offer < floor` → **reject**, `final: true`

Every response includes `reasoning` (short human string) and `final` (boolean).

## Simple strategy (fallback / config option)

- If `carrier_offer ≥ loadboard_rate × 0.95` → **accept**
- Else → **counter** at `loadboard_rate × 0.97` regardless of round
- Round 3: accept if above floor, else reject

## Worked examples (smart strategy)

Load: `loadboard_rate = $2,000`, floor = $1,840, target = $1,960.

**Example A — quick accept**
- Round 1: carrier offers $1,970 → `$1,970 ≥ target` → **accept $1,970**

**Example B — two-round agreement**
- Round 1: carrier offers $1,900 → above floor, below target → **counter** at `($1,900 + $2,000) / 2 = $1,950`
- Round 2: carrier offers $1,930 → above floor, below target → **counter** at `$1,930 + ($1,950 - $1,930) × 0.5 = $1,940`
- Round 3: carrier offers $1,940 → above floor → **accept $1,940**

**Example C — lowball, walk away**
- Round 1: carrier offers $1,700 → below floor → **counter** at $1,960
- Round 2: carrier offers $1,750 → below floor → **counter** at $1,858 (floor × 1.01)
- Round 3: carrier offers $1,800 → below floor → **reject, final**

**Example D — reasonable carrier, amicable close**
- Round 1: carrier offers $1,950 → above floor, below target → **counter** at $1,975
- Round 2: carrier offers $1,965 → above target → **accept $1,965**

## Edge cases

- **Carrier offers exactly the loadboard rate:** accept (it's above target by definition).
- **Carrier offers above loadboard rate:** accept (rare but possible — take the money).
- **Negative or zero offer:** return `400 invalid_offer`.
- **Round number > 3:** return `400 invalid_round`.
- **Same offer twice in a row:** still process per round rules; agent should detect and move on, but backend is stateless on this.

## What the agent says to the carrier

The backend returns the **decision** and **counter price**. The HappyRobot agent is responsible for phrasing. Suggested scripts in `HAPPYROBOT.md`:

- Accept: *"Great, we have a deal at $X. Let me transfer you to a rep."*
- Counter: *"I can't quite do that, but I can meet you at $X."*
- Reject (final): *"Unfortunately we can't go that low. Thanks for calling — please reach out for future loads."*

## Metrics this feeds

- `avg_negotiation_rounds` per outcome
- `avg_delta_from_loadboard` = `(final_price - loadboard_rate) / loadboard_rate`
- Distribution of round-at-accept (did deals close in round 1, 2, or 3?)
- Broker-declined count (how often we walked away)

These live in the Exec dashboard tab.
