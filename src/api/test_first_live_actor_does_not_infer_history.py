from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def main():
    hand = CanonicalHand().start_hand(
        hand_id="first-live-actor-sync",
        players=[
            {
                "seat": "utg",
                "name": "UTG",
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
        hero_cards=["2c", "9s"],
        hero_position="BB",
        positions={
            "utg": "UTG",
            "hj": "HJ",
            "co": "CO",
            "btn": "BTN",
            "sb": "SB",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    # Exact live failure shape:
    #
    # The canonical poker traversal exists before perception has
    # synchronized to the current physical action point.
    hand.players_to_act = [
        "utg",
        "hj",
        "co",
        "btn",
        "sb",
        "hero",
    ]

    tracker = BettingRoundTracker(hand)

    before_queue = list(hand.players_to_act)
    before_actions = list(hand.actions)

    added = tracker.advance_to_observed_actor(
        "hero",
        blocked_seats=set(),
        ts=10.0,
    )

    print("before_queue:", before_queue)
    print("after_queue:", hand.players_to_act)
    print(
        "added:",
        [
            (action.seat, action.action)
            for action in added
        ],
    )

    false_actions = [
        action
        for action in hand.actions[len(before_actions):]
        if action.seat in {
            "utg",
            "hj",
            "co",
            "btn",
            "sb",
        }
    ]

    assert false_actions == [], (
        "RED: first observed live actor fabricated historical "
        "predecessor actions: "
        + repr([
            (action.seat, action.action)
            for action in false_actions
        ])
    )

    assert hand.players_to_act == before_queue, (
        "first observed actor has no authority to consume "
        "unowned predecessor betting obligations: "
        + repr(hand.players_to_act)
    )

    for seat in [
        "utg",
        "hj",
        "co",
        "btn",
        "sb",
    ]:
        player = hand.players[seat]

        assert player.active is True, (
            f"{seat} was incorrectly made inactive during "
            "live chronology synchronization"
        )

        assert player.folded is False, (
            f"{seat} was incorrectly folded during "
            "live chronology synchronization"
        )

    print(
        "PASS: first live actor establishes synchronization "
        "without manufacturing predecessor history"
    )


if __name__ == "__main__":
    main()
