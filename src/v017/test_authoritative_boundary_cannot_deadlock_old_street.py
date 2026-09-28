"""
Regression for the live v0.17 frame-142 street deadlock.

An authoritative next-street board proves the prior betting round has
physically ended. It must not leave semantic chronology permanently on
the old street merely because the remaining actor was facing a price.

The boundary alone must NOT guess CALL versus FOLD.
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "hero",
        "position": "CO",
        "name": "Hero",
        "stack_bb": 40.0,
        "dealt_in": True,
    },
    {
        "seat": "btn",
        "position": "BTN",
        "name": "BTN",
        "stack_bb": 70.0,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 100.0,
        "dealt_in": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 100.0,
        "dealt_in": True,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "btn",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 40.0,
            "btn": 70.0,
            "sb": 100.0,
            "bb": 100.0,
        },
        opponent_seats=[
            "btn",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "hero",
            "btn",
            "sb",
            "bb",
        ],
        hero_seat="hero",
        hand_id="authoritative-boundary-liveness",
    )

    # Hero raises from 0 -> 1.75 BB.
    admitted = observer.admit_quantitative_observation(
        {
            "frame": 10,
            "type": "STACK_QUANTITATIVE_OBSERVATION",
            "seat": "hero",
            "resolved": True,
            "resolved_value": 38.25,
        }
    )

    assert admitted
    assert observer.hand.current_price_bb == 1.75

    # BTN and SB objectively fold.
    observer.admit_card_disappearance(
        "btn",
        frame_id=11,
    )
    observer.admit_card_disappearance(
        "sb",
        frame_id=12,
    )

    assert observer.hand.next_actor == "bb"

    before = list(
        observer.hand.semantic_actions()
    )

    # Physical flop + authoritative board identity.
    result = observer.admit_street_boundary(
        {
            "frame": 13,
            "type": "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
        },
        action_order=[
            "bb",
            "hero",
        ],
        board=[
            "Qc",
            "3c",
            "6c",
        ],
        complete_pending=True,
    )

    after = list(
        observer.hand.semantic_actions()
    )

    print("street =", observer.hand.street)
    print("next_actor =", observer.hand.next_actor)
    print(
        "pending_boundaries =",
        len(observer.pending_street_boundaries),
    )
    print(
        "actions_added_by_boundary =",
        after[len(before):],
    )

    # A board boundary alone cannot manufacture BB CALL/FOLD.
    added = after[len(before):]

    assert not any(
        row.get("seat") == "bb"
        and row.get("action") in {
            "CALL",
            "FOLD",
        }
        for row in added
    ), (
        "authoritative boundary guessed BB CALL/FOLD"
    )

    # But confirmed FLOP authority cannot leave semantic PREFLOP
    # indefinitely either.
    assert observer.hand.street == "FLOP", (
        "authoritative FLOP left semantic chronology "
        "deadlocked on PREFLOP"
    )

    assert not observer.pending_street_boundaries, (
        "authoritative FLOP remained pending"
    )

    assert result, (
        "authoritative FLOP produced no semantic transition"
    )

    print(
        "NON-ZERO ACTION GUESSED: NO"
    )
    print(
        "OLD STREET DEADLOCKED: NO"
    )
    print(
        "V0.17 AUTHORITATIVE BOUNDARY LIVENESS: PASS"
    )


if __name__ == "__main__":
    main()
