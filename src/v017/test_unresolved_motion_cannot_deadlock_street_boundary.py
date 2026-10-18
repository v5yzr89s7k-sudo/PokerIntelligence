"""
Regression for 2026-10-17 live certification stall.

Contract:

    unresolved physical stack motion
    + bounded quantitative retries exhausted
    + no authoritative CALL/FOLD classification
    + objective next-street boundary arrives

must NOT permanently deadlock chronology.

The boundary may close unresolved predecessor chronology only through
existing street-boundary completion authority. It must never convert
ambiguous motion/card disappearance into CALL or FOLD.
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "villain",
        "position": "BB",
        "name": "Villain",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["hero", "villain"],
        small_blind_seat="hero",
        big_blind_seat="villain",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 49.5,
            "villain": 49.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=["villain"],
        hero_seat="hero",
        hand_id="unresolved-motion-boundary-liveness",
    )

    # Hero completes SB; BB remains the authoritative actor.
    observer.hand.observe_stack_commitment(
        "hero",
        0.5,
    )

    assert observer.hand.next_actor == "villain"

    before = list(observer.hand.semantic_actions())

    # Reproduce the post-retry-exhaustion state:
    # physical motion remains real, but quantitative classification
    # could not be completed.
    observer.unresolved_quantitative_motion["villain"] = {
        "first_frame": 8,
        "last_frame": 15,
        "reason": "stack_motion",
        "commitment_seen": True,
    }

    assert "villain" not in observer.quantitative_retry_pending
    assert "villain" not in observer.quantitative_confirmation_pending

    # Card disappearance is also physically observed. It must NOT be
    # promoted to FOLD merely because bounded OCR ownership ended.
    observer._retain_pending_card_disappearance(
        "villain",
        frame_id=16,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    observer.reconcile_pending_card_disappearances()

    assert observer.hand.next_actor == "villain"
    assert not observer.hand.players["villain"].folded

    # Objective next-street chronology now proves the predecessor
    # street is over. It may close unknown predecessor completion,
    # but must not invent CALL or FOLD.
    observer.admit_street_boundary(
        {
            "frame": 20,
            "type": "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
            "previous_board_count": 0,
        },
        action_order=["villain", "hero"],
        board=None,
        complete_pending=True,
    )

    after = list(observer.hand.semantic_actions())
    added = after[len(before):]

    assert observer.hand.street == "FLOP", (
        "RED: unresolved physical motion permanently "
        "deadlocked objective FLOP chronology"
    )

    assert not any(
        row.get("seat") == "villain"
        and row.get("action") in {"CALL", "FOLD"}
        for row in added
    ), (
        "RED: street-boundary liveness guessed "
        "ambiguous villain CALL/FOLD"
    )

    print("UNRESOLVED MOTION FABRICATED CALL/FOLD: NO")
    print("OBJECTIVE STREET BOUNDARY DEADLOCKED: NO")
    print(
        "V0.17 UNRESOLVED MOTION STREET "
        "BOUNDARY LIVENESS: PASS"
    )


if __name__ == "__main__":
    main()
