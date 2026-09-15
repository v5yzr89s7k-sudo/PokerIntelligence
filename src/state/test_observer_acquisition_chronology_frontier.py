"""
v0.16 observer-acquisition chronology frontier contract.

The observer may attach after some legal preflop obligations have already
occurred outside owned observation.

Those predecessor actions remain UNKNOWN. They must not be fabricated as
folds/checks/calls/etc., but they also must not permanently block later
physical actions that are genuinely observed after acquisition.
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


def make_hand():
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
        hand_id="acquisition-frontier-contract",
        players=players,
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions=POSITIONS,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(POSITIONS)
    hand.current_street = "PREFLOP"

    return hand


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


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    expected_full_queue = [
        "utg",
        "lj",
        "hj",
        "co",
        "btn",
        "sb",
        "hero",
    ]

    assert hand.players_to_act == expected_full_queue, (
        "test setup failed: unexpected legal preflop queue "
        f"{hand.players_to_act}"
    )

    # First owned raw opponent-card state:
    #
    # UTG absent
    # LJ  absent
    # HJ  absent
    # CO  present
    # BTN present
    # SB  present
    # Hero active
    #
    # Therefore the observer owns chronology beginning at CO.
    #
    # This API intentionally does not exist yet.
    result = tracker.establish_observer_acquisition_frontier(
        street="PREFLOP",
        first_owned_seat="co",
        pre_acquisition_seats=["utg", "lj", "hj"],
        ts=10.0,
    )

    assert result is not None

    # Unknown history must remain unknown. Establishing the frontier may
    # change chronology ownership, but it may not invent poker actions.
    assert voluntary_actions(hand) == [], (
        "acquisition frontier fabricated voluntary history: "
        f"{[(a.seat, a.action) for a in voluntary_actions(hand)]}"
    )

    # Pre-acquisition seats are no longer live obligations.
    assert hand.players_to_act == [
        "co",
        "btn",
        "sb",
        "hero",
    ], (
        "pre-acquisition history still blocks owned chronology: "
        f"{hand.players_to_act}"
    )

    status = tracker.commitment_tracker.round_status("PREFLOP")

    assert status.get("players_owing_action") == [
        "co",
        "btn",
        "sb",
        "hero",
    ], (
        "StreetCommitmentTracker disagrees with acquisition frontier: "
        f"{status.get('players_owing_action')}"
    )

    # No canonical action may exist for the unknown predecessor seats.
    predecessor_actions = [
        (action.seat, action.action)
        for action in voluntary_actions(hand)
        if action.seat in {"utg", "lj", "hj"}
    ]

    assert predecessor_actions == [], (
        "pre-acquisition seats acquired fabricated semantics: "
        f"{predecessor_actions}"
    )

    # The first genuinely owned physical actor must now be chronology head.
    assert hand.players_to_act[0] == "co"

    print()
    print("PASS: observer acquisition frontier contract")
    print("pre_acquisition=['utg', 'lj', 'hj']")
    print("owned_queue=['co', 'btn', 'sb', 'hero']")
    print("fabricated_actions=[]")


if __name__ == "__main__":
    main()
