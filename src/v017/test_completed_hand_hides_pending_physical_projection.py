"""
Completed-hand presentation ownership regression.

Once HandEngine owns authoritative hand completion, unresolved physical
evidence must not remain visible as CANONICAL ORDER PENDING.
"""

from src.v017.frame_hand_observer import FrameHandObserver


def main():
    observer = FrameHandObserver(
        players=[
            {
                "seat": "villain",
                "position": "BTN",
                "name": "Villain",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
            {
                "seat": "hero",
                "position": "BB",
                "name": "Hero",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
        ],
        action_order=[
            "villain",
            "hero",
        ],
        small_blind_seat="villain",
        big_blind_seat="hero",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "villain": 50.0,
            "hero": 50.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=[
            "villain",
            "hero",
        ],
        hero_seat="hero",
        hand_id="completed-hand-pending-projection",
    )

    # Retain physical evidence that cannot yet cross chronology.
    observer.admit_card_disappearance(
        "hero",
        frame_id=10,
        physical_type="HERO_CARDS_DISAPPEARED_PHYSICAL",
    )

    before = observer.render_live_projection()

    assert (
        "PHYSICALLY OBSERVED — CANONICAL ORDER PENDING"
        in before
    ), "test setup failed: no pending projection"

    # Establish authoritative uncontested completion through the
    # canonical HandEngine path.
    observer.admit_card_disappearance(
        "villain",
        frame_id=11,
        physical_type="OPPONENT_CARDS_DISAPPEARED_PHYSICAL",
    )

    assert observer.hand.hand_complete

    completed = observer.render_live_projection()

    assert (
        "PHYSICALLY OBSERVED — CANONICAL ORDER PENDING"
        not in completed
    ), (
        "RED: completed canonical hand still renders stale "
        "pending physical evidence"
    )

    print(
        "COMPLETED HAND PENDING PHYSICAL PROJECTION: HIDDEN"
    )
    print(
        "V0.17 TERMINAL PRESENTATION OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
