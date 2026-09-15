from src.state.betting_round_tracker import BettingRoundTracker
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="observed-actor-predecessor-authority",
        players=[
            {
                "seat": "utg",
                "name": "UTG",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "lj",
                "name": "LJ",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "hj",
                "name": "HJ",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "co",
                "name": "CO",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "btn",
                "name": "BTN",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "sb",
                "name": "SB",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions={
            "utg": "UTG",
            "lj": "LJ",
            "hj": "HJ",
            "co": "CO",
            "btn": "BTN",
            "sb": "SB",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.players_to_act = [
        "utg",
        "lj",
        "hj",
        "co",
        "btn",
        "sb",
        "hero",
    ]

    return hand


def assert_no_unowned_consumption(
    tracker,
    hand,
    expected_queue,
    label,
):
    assert hand.players_to_act == expected_queue, (
        f"RED {label}: actor observation consumed "
        f"unowned predecessor obligations: "
        f"{hand.players_to_act}"
    )

    owing = (
        tracker.commitment_tracker
        .players_owing_action("PREFLOP")
    )

    assert owing == expected_queue, (
        f"RED {label}: commitment tracker consumed "
        f"unowned predecessor obligations: {owing}"
    )

    assert hand.actions == [], (
        f"RED {label}: actor observation created "
        f"canonical actions: {hand.actions}"
    )


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    original_queue = list(hand.players_to_act)

    # Sep 8 shape:
    #
    # We first physically notice CO while UTG/LJ/HJ have
    # no ActionTimeline owner and no card-disappearance
    # completion evidence.
    result = tracker.advance_to_observed_actor(
        "co",
        ts=10.0,
        blocked_seats=[],
    )

    assert result == []

    assert_no_unowned_consumption(
        tracker,
        hand,
        original_queue,
        "first later actor",
    )

    # Repeated observation progress must not tunnel through
    # the unresolved gap either.
    result = tracker.advance_to_observed_actor(
        "btn",
        ts=11.0,
        blocked_seats=[],
    )

    assert result == []

    assert_no_unowned_consumption(
        tracker,
        hand,
        original_queue,
        "second later actor",
    )

    result = tracker.advance_to_observed_actor(
        "sb",
        ts=12.0,
        blocked_seats=[],
    )

    assert result == []

    assert_no_unowned_consumption(
        tracker,
        hand,
        original_queue,
        "third later actor",
    )

    print(
        "PASS: later actor observations cannot consume "
        "unowned predecessor action obligations"
    )


if __name__ == "__main__":
    main()
