from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

Action = Literal["accept", "counter", "reject"]

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class NegotiationInputs:
    loadboard_rate: Decimal
    carrier_offer: Decimal
    round_number: int
    last_counter: Decimal | None
    floor_pct: Decimal
    target_pct: Decimal


@dataclass(frozen=True)
class NegotiationDecision:
    action: Action
    counter_price: Decimal | None
    reasoning: str
    final: bool


def _q(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def decide(i: NegotiationInputs) -> NegotiationDecision:
    """Apply the locked smart negotiation policy. Input is assumed valid.

    Callers MUST validate round_number ∈ {1,2,3} and carrier_offer > 0
    upstream (the router returns structured 400s). This function trusts
    its input so unit tests exercise the pure policy logic.
    """
    floor = _q(i.loadboard_rate * i.floor_pct)
    target = _q(i.loadboard_rate * i.target_pct)
    offer = i.carrier_offer

    if i.round_number == 1:
        if offer >= target:
            return NegotiationDecision(
                action="accept",
                counter_price=None,
                reasoning=f"Round 1: offer {offer} at or above target {target}; instant accept.",
                final=True,
            )
        if offer >= floor:
            counter = _q((offer + i.loadboard_rate) / Decimal("2"))
            return NegotiationDecision(
                action="counter",
                counter_price=counter,
                reasoning=(
                    f"Round 1: offer {offer} above floor {floor} but below target {target}; "
                    f"countering at midpoint of offer and loadboard {i.loadboard_rate}."
                ),
                final=False,
            )
        return NegotiationDecision(
            action="counter",
            counter_price=target,
            reasoning=(
                f"Round 1: offer {offer} below floor {floor}; "
                f"signalling with a counter at target {target}."
            ),
            final=False,
        )

    if i.round_number == 2:
        if offer >= target:
            return NegotiationDecision(
                action="accept",
                counter_price=None,
                reasoning=f"Round 2: offer {offer} at or above target {target}; accept.",
                final=True,
            )
        if offer >= floor:
            last = i.last_counter if i.last_counter is not None else _q(
                (offer + i.loadboard_rate) / Decimal("2")
            )
            concession = (last - offer) * Decimal("0.5")
            counter = _q(offer + concession)
            return NegotiationDecision(
                action="counter",
                counter_price=counter,
                reasoning=(
                    f"Round 2: conceding half the remaining gap from our last counter {last} "
                    f"toward offer {offer}; new counter {counter}."
                ),
                final=False,
            )
        final_signal = _q(floor * Decimal("1.01"))
        return NegotiationDecision(
            action="counter",
            counter_price=final_signal,
            reasoning=(
                f"Round 2: offer {offer} still below floor {floor}; "
                f"one more signal at floor+1% = {final_signal}."
            ),
            final=False,
        )

    # round 3 — final
    if offer >= floor:
        return NegotiationDecision(
            action="accept",
            counter_price=None,
            reasoning=f"Round 3 final: offer {offer} at or above floor {floor}; taking the deal.",
            final=True,
        )
    return NegotiationDecision(
        action="reject",
        counter_price=None,
        reasoning=f"Round 3 final: offer {offer} below floor {floor}; walking away.",
        final=True,
    )
