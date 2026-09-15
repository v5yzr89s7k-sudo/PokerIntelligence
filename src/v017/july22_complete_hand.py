"""
Complete July 22 reference hand.

Constructed exclusively through HandEngine's public observation API.
No legacy semantic system and no direct internal-state mutation.
"""

from src.v017.hand_engine import HandEngine
from src.v017.test_july22_preflop_vertical_slice import (
    PLAYERS,
    ACTION_ORDER,
)


HERO_CARDS = [
    "Qd",
    "Ah",
]

FLOP = [
    "Jd",
    "9s",
    "Tc",
]

TURN_BOARD = [
    "Jd",
    "9s",
    "Tc",
    "9h",
]

RIVER_BOARD = [
    "Jd",
    "9s",
    "Tc",
    "9h",
    "7h",
]


def build_complete_july22_hand():
    hand = HandEngine(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
    )

    hand.observe_hero_cards(
        HERO_CARDS
    )

    # Physical July 22 card-back evidence:
    # seat_mid_left / Fartsenia was seated but never showed
    # opponent hole cards in any recorded frame.
    hand.players[
        "seat_mid_left"
    ].dealt_in = False

    # ------------------------------------------------------------
    # PREFLOP
    # ------------------------------------------------------------

    assert (
        hand.observe_cards_disappeared(
            "seat_upper_left"
        )
        == "FOLD"
    )

    assert (
        hand.observe_cards_disappeared(
            "seat_upper_right"
        )
        == "FOLD"
    )

    assert (
        hand.observe_cards_disappeared(
            "seat_mid_right"
        )
        == "FOLD"
    )

    assert (
        hand.observe_stack_commitment(
            "seat_lower_right",
            2.0,
        )
        == "RAISE"
    )

    assert (
        hand.observe_stack_commitment(
            "hero",
            1.5,
        )
        == "CALL"
    )

    assert (
        hand.observe_stack_commitment(
            "seat_lower_left",
            1.0,
        )
        == "CALL"
    )

    assert hand.next_actor is None

    # ------------------------------------------------------------
    # FLOP
    # ------------------------------------------------------------

    hand.start_street(
        "FLOP",
        [
            "hero",
            "seat_lower_left",
            "seat_lower_right",
        ],
        board=FLOP,
    )

    assert (
        hand.observe_no_commitment(
            "hero"
        )
        == "CHECK"
    )

    assert (
        hand.observe_stack_commitment(
            "seat_lower_left",
            3.37,
        )
        == "BET"
    )

    assert (
        hand.observe_cards_disappeared(
            "seat_lower_right"
        )
        == "FOLD"
    )

    assert (
        hand.observe_stack_commitment(
            "hero",
            3.37,
        )
        == "CALL"
    )

    assert hand.next_actor is None

    # ------------------------------------------------------------
    # TURN
    # ------------------------------------------------------------

    hand.start_street(
        "TURN",
        [
            "hero",
            "seat_lower_left",
        ],
        board=TURN_BOARD,
    )

    assert (
        hand.observe_no_commitment(
            "hero"
        )
        == "CHECK"
    )

    assert (
        hand.observe_no_commitment(
            "seat_lower_left"
        )
        == "CHECK"
    )

    assert hand.next_actor is None

    # ------------------------------------------------------------
    # RIVER
    # ------------------------------------------------------------

    hand.start_street(
        "RIVER",
        [
            "hero",
            "seat_lower_left",
        ],
        board=RIVER_BOARD,
    )

    assert (
        hand.observe_no_commitment(
            "hero"
        )
        == "CHECK"
    )

    assert (
        hand.observe_stack_commitment(
            "seat_lower_left",
            6.75,
        )
        == "BET"
    )

    assert (
        hand.observe_fold(
            "hero"
        )
        == "FOLD"
    )

    assert hand.next_actor is None

    return hand
