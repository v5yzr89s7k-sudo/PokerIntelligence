"""
Safety contracts for observer-acquisition chronology ownership.

The acquisition frontier may release only the exact legal prefix that
predates owned observation.

It must be:
- semantic-free,
- exact-prefix only,
- same-street only,
- idempotent for the identical frontier,
- immutable after establishment.
"""

from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


POSITIONS = {
    "utg": "UTG",
    "lj": "LJ",
    "hj": "HJ",
    "co": "CO",
    "btn": "BTN",
    "sb": "SB",
    "hero": "BB",
}

FULL_QUEUE = [
    "utg",
    "lj",
    "hj",
    "co",
    "btn",
    "sb",
    "hero",
]


def make_tracker():
    players = [
        {
            "seat": seat,
            "name": seat.upper(),
            "stack_bb": 100.0,
            "is_hero": seat == "hero",
            "is_active": True,
        }
        for seat in POSITIONS
    ]

    hand = CanonicalHand().start_hand(
        hand_id="acquisition-frontier-safety",
        players=players,
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions=POSITIONS,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(POSITIONS)
    hand.current_street = "PREFLOP"

    return hand, BettingRoundTracker(hand)


def voluntary_actions(hand):
    forced = {
        "POST_ANTE",
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
    }

    return [
        action
        for action in hand.actions
        if action.action not in forced
    ]


def require_value_error(fn, expected_fragment):
    try:
        fn()
    except ValueError as exc:
        message = str(exc)
        assert expected_fragment in message, (
            f"wrong ValueError: {message!r}"
        )
        return message

    raise AssertionError(
        f"expected ValueError containing {expected_fragment!r}"
    )


def test_exact_prefix_required():
    hand, tracker = make_tracker()

    before = list(hand.players_to_act)

    message = require_value_error(
        lambda: tracker.establish_observer_acquisition_frontier(
            street="PREFLOP",
            first_owned_seat="co",
            # Deliberately omit LJ. This must never be accepted.
            pre_acquisition_seats=["utg", "hj"],
            ts=10.0,
        ),
        "acquisition_frontier_prefix_mismatch",
    )

    assert before == FULL_QUEUE
    assert hand.players_to_act == FULL_QUEUE
    assert voluntary_actions(hand) == []
    assert tracker.observer_acquisition_frontier is None

    print("PASS exact-prefix guard:", message)


def test_wrong_street_rejected():
    hand, tracker = make_tracker()

    message = require_value_error(
        lambda: tracker.establish_observer_acquisition_frontier(
            street="FLOP",
            first_owned_seat="co",
            pre_acquisition_seats=["utg", "lj", "hj"],
            ts=10.0,
        ),
        "acquisition_frontier_street_mismatch",
    )

    assert hand.players_to_act == FULL_QUEUE
    assert voluntary_actions(hand) == []
    assert tracker.observer_acquisition_frontier is None

    print("PASS street guard:", message)


def test_first_owned_must_exist():
    hand, tracker = make_tracker()

    message = require_value_error(
        lambda: tracker.establish_observer_acquisition_frontier(
            street="PREFLOP",
            first_owned_seat="ghost",
            pre_acquisition_seats=FULL_QUEUE,
            ts=10.0,
        ),
        "acquisition_frontier_first_owned_not_in_queue",
    )

    assert hand.players_to_act == FULL_QUEUE
    assert voluntary_actions(hand) == []
    assert tracker.observer_acquisition_frontier is None

    print("PASS first-owned guard:", message)


def test_identical_frontier_is_idempotent():
    hand, tracker = make_tracker()

    first = tracker.establish_observer_acquisition_frontier(
        street="PREFLOP",
        first_owned_seat="co",
        pre_acquisition_seats=["utg", "lj", "hj"],
        ts=10.0,
    )

    queue_after_first = list(hand.players_to_act)

    second = tracker.establish_observer_acquisition_frontier(
        street="PREFLOP",
        first_owned_seat="co",
        pre_acquisition_seats=["utg", "lj", "hj"],
        ts=10.0,
    )

    assert first == second
    assert queue_after_first == [
        "co",
        "btn",
        "sb",
        "hero",
    ]
    assert hand.players_to_act == queue_after_first
    assert voluntary_actions(hand) == []

    status = tracker.commitment_tracker.round_status(
        "PREFLOP"
    )

    assert status.get("players_owing_action") == queue_after_first

    print("PASS identical frontier idempotency")


def test_frontier_cannot_move_later():
    hand, tracker = make_tracker()

    tracker.establish_observer_acquisition_frontier(
        street="PREFLOP",
        first_owned_seat="co",
        pre_acquisition_seats=["utg", "lj", "hj"],
        ts=10.0,
    )

    before = list(hand.players_to_act)

    message = require_value_error(
        lambda: tracker.establish_observer_acquisition_frontier(
            street="PREFLOP",
            first_owned_seat="btn",
            pre_acquisition_seats=[
                "utg",
                "lj",
                "hj",
                "co",
            ],
            ts=11.0,
        ),
        "acquisition_frontier_already_established",
    )

    assert before == [
        "co",
        "btn",
        "sb",
        "hero",
    ]
    assert hand.players_to_act == before
    assert voluntary_actions(hand) == []

    print("PASS immutable frontier guard:", message)


def test_frontier_does_not_mutate_player_semantics():
    hand, tracker = make_tracker()

    before = {
        seat: (
            player.folded,
            player.active,
            player.all_in,
        )
        for seat, player in hand.players.items()
    }

    tracker.establish_observer_acquisition_frontier(
        street="PREFLOP",
        first_owned_seat="co",
        pre_acquisition_seats=["utg", "lj", "hj"],
        ts=10.0,
    )

    after = {
        seat: (
            player.folded,
            player.active,
            player.all_in,
        )
        for seat, player in hand.players.items()
    }

    assert after == before
    assert voluntary_actions(hand) == []

    for seat in ("utg", "lj", "hj"):
        player = hand.players[seat]
        assert player.folded is False
        assert player.active is True
        assert player.all_in is False

    print("PASS frontier is semantic-free")


def main():
    test_exact_prefix_required()
    test_wrong_street_rejected()
    test_first_owned_must_exist()
    test_identical_frontier_is_idempotent()
    test_frontier_cannot_move_later()
    test_frontier_does_not_mutate_player_semantics()

    print()
    print("PASS: acquisition frontier safety contracts")


if __name__ == "__main__":
    main()
