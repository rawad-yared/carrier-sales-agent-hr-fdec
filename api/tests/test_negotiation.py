"""Unit tests for the negotiation policy — pure `decide()` calls, no HTTP.

Worked examples taken verbatim from docs/NEGOTIATION.md. Loadboard $2,000,
floor 0.92 → $1,840, target 0.98 → $1,960.
"""
from decimal import Decimal

import pytest

from app.services.negotiation import NegotiationInputs, decide

FLOOR_PCT = Decimal("0.92")
TARGET_PCT = Decimal("0.98")
LOADBOARD = Decimal("2000.00")


def _make(offer: str, round_number: int, last_counter: str | None = None) -> NegotiationInputs:
    return NegotiationInputs(
        loadboard_rate=LOADBOARD,
        carrier_offer=Decimal(offer),
        round_number=round_number,
        last_counter=Decimal(last_counter) if last_counter is not None else None,
        floor_pct=FLOOR_PCT,
        target_pct=TARGET_PCT,
    )


# ------------------------------------------------------------------------
# Example A — quick accept
# ------------------------------------------------------------------------
def test_example_a_round1_at_target_is_instant_accept():
    d = decide(_make("1970.00", round_number=1))
    assert d.action == "accept"
    assert d.counter_price is None
    assert d.final is True


# ------------------------------------------------------------------------
# Example B — two-round agreement
# ------------------------------------------------------------------------
def test_example_b_round1_above_floor_counters_at_midpoint():
    d = decide(_make("1900.00", round_number=1))
    assert d.action == "counter"
    assert d.counter_price == Decimal("1950.00")
    assert d.final is False


def test_example_b_round2_concedes_half_the_gap():
    # Round 1 countered at $1,950; carrier now offers $1,930
    # new = 1930 + (1950 - 1930) * 0.5 = 1940
    d = decide(_make("1930.00", round_number=2, last_counter="1950.00"))
    assert d.action == "counter"
    assert d.counter_price == Decimal("1940.00")
    assert d.final is False


def test_example_b_round3_above_floor_accepts():
    d = decide(_make("1940.00", round_number=3))
    assert d.action == "accept"
    assert d.counter_price is None
    assert d.final is True


# ------------------------------------------------------------------------
# Example C — lowball, walk away
# ------------------------------------------------------------------------
def test_example_c_round1_below_floor_counters_at_target():
    d = decide(_make("1700.00", round_number=1))
    assert d.action == "counter"
    assert d.counter_price == Decimal("1960.00")  # target
    assert d.final is False


def test_example_c_round2_below_floor_signals_at_floor_plus_1pct():
    d = decide(_make("1750.00", round_number=2, last_counter="1960.00"))
    assert d.action == "counter"
    # floor = 1840, floor * 1.01 = 1858.40
    assert d.counter_price == Decimal("1858.40")
    assert d.final is False


def test_example_c_round3_below_floor_rejects_final():
    d = decide(_make("1800.00", round_number=3))
    assert d.action == "reject"
    assert d.counter_price is None
    assert d.final is True


# ------------------------------------------------------------------------
# Example D — amicable close
# ------------------------------------------------------------------------
def test_example_d_round1_counter_midpoint():
    d = decide(_make("1950.00", round_number=1))
    assert d.action == "counter"
    # (1950 + 2000) / 2 = 1975
    assert d.counter_price == Decimal("1975.00")


def test_example_d_round2_at_target_accepts():
    d = decide(_make("1965.00", round_number=2, last_counter="1975.00"))
    assert d.action == "accept"
    assert d.final is True


# ------------------------------------------------------------------------
# Edges
# ------------------------------------------------------------------------
def test_offer_exactly_at_loadboard_round1_accepts():
    d = decide(_make("2000.00", round_number=1))
    assert d.action == "accept"


def test_offer_above_loadboard_accepts():
    d = decide(_make("2100.00", round_number=1))
    assert d.action == "accept"


def test_offer_exactly_at_target_round1_accepts():
    d = decide(_make("1960.00", round_number=1))
    assert d.action == "accept"


def test_offer_exactly_at_floor_round1_counters():
    # at floor → above floor check is ≥, so this counters at midpoint
    d = decide(_make("1840.00", round_number=1))
    assert d.action == "counter"
    # (1840 + 2000) / 2 = 1920
    assert d.counter_price == Decimal("1920.00")


def test_offer_exactly_at_floor_round3_accepts():
    d = decide(_make("1840.00", round_number=3))
    assert d.action == "accept"
    assert d.final is True


def test_round2_without_last_counter_falls_back_gracefully():
    # History missing (shouldn't happen in practice, but must not crash)
    d = decide(_make("1900.00", round_number=2, last_counter=None))
    assert d.action == "counter"
    assert d.counter_price is not None


def test_decision_is_always_final_when_action_is_not_counter():
    accept = decide(_make("1970.00", round_number=1))
    reject = decide(_make("1500.00", round_number=3))
    counter = decide(_make("1900.00", round_number=1))
    assert accept.final is True
    assert reject.final is True
    assert counter.final is False
