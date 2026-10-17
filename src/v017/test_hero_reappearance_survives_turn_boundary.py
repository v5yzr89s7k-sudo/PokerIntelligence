"""
Behavioral regression from the live 2026-10-15 hand.

Observed physical chronology:

    frame 465:
        transient Hero-card disappearance retained while
        prior FLOP chronology was already closed

    frame 468:
        Hero action buttons visible again, objectively proving
        Hero remains active

    frame 490:
        physical TURN boundary appears

Production must never allow the stale frame-465 disappearance to
become a Hero FOLD when TURN chronology activates.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "Villain",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]


def build_observer():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=["bb"],
        quantitative_seats=[
            "hero",
            "bb",
        ],
        hero_seat="hero",
        hand_id=(
            "hero-reappearance-"
            "survives-turn-boundary"
        ),
    )

    # Close PREFLOP without folding either player.
    observer.hand.resolve_boundary_completed_actor(
        "hero"
    )
    observer.hand.resolve_boundary_completed_actor(
        "bb"
    )

    observer.hand.start_street(
        "FLOP",
        [
            "hero",
            "bb",
        ],
        board=[
            "Kd",
            "9d",
            "2c",
        ],
    )

    # Model the completed live FLOP: both players remain active.
    observer.hand.resolve_boundary_completed_actor(
        "hero"
    )
    observer.hand.resolve_boundary_completed_actor(
        "bb"
    )

    assert observer.hand.street == "FLOP"
    assert observer.hand.next_actor is None
    assert not observer.hand.hand_complete

    return observer


def main():
    observer = build_observer()

    actions_before = len(
        observer.hand.semantic_actions()
    )

    # --------------------------------------------------------
    # FRAME 465
    #
    # Hero disappears transiently while no actor is currently
    # authoritative. Physical evidence is retained only.
    # --------------------------------------------------------

    observer.retain_card_disappearance(
        "hero",
        frame_id=465,
        physical_type=(
            "HERO_CARDS_DISAPPEARED_PHYSICAL"
        ),
    )

    assert len(
        observer.pending_card_disappearances
    ) == 1

    assert (
        len(observer.hand.semantic_actions())
        == actions_before
    )

    assert not observer.hand.hand_complete

    print(
        "FRAME 465 TRANSIENT HERO DISAPPEARANCE "
        "RETAINED: PASS"
    )

    # --------------------------------------------------------
    # FRAME 468
    #
    # Positive Hero-turn evidence supersedes the older retained
    # disappearance.
    # --------------------------------------------------------

    invalidated = (
        observer
        .invalidate_retained_hero_disappearance(
            frame_id=468,
            reason="action_buttons_visible",
        )
    )

    assert len(invalidated) == 1
    assert (
        observer.pending_card_disappearances
        == []
    )

    assert (
        len(observer.hand.semantic_actions())
        == actions_before
    )

    assert not observer.hand.hand_complete

    print(
        "FRAME 468 HERO ACTIVE EVIDENCE "
        "INVALIDATES STALE DISAPPEARANCE: PASS"
    )

    # --------------------------------------------------------
    # FRAME 490
    #
    # TURN boundary must cross without resurrecting frame 465
    # as a fold.
    # --------------------------------------------------------

    admitted = observer.admit_street_boundary(
        {
            "frame": 490,
            "type":
                "TURN_BOUNDARY_PHYSICAL",
            "board_count": 4,
            "previous_board_count": 3,
        },
        action_order=[
            "hero",
            "bb",
        ],
        board=[
            "Kd",
            "9d",
            "2c",
            "6s",
        ],
        complete_pending=False,
    )

    assert observer.hand.street == "TURN"

    # Street admission may return boundary events, but must not
    # create a stale Hero fold.
    assert (
        observer.pending_card_disappearances
        == []
    )

    hero_folds = [
        row
        for row
        in observer.hand.semantic_actions()
        if (
            row.get("seat") == "hero"
            and row.get("action") == "FOLD"
        )
    ]

    assert hero_folds == [], hero_folds

    assert not observer.hand.hand_complete

    assert (
        observer.hand.players["hero"].folded
        is False
    )

    assert observer.hand.next_actor == "hero"

    assert (
        len(observer.hand.semantic_actions())
        == actions_before
    )

    print(
        "FRAME 490 TURN CROSSES WITHOUT "
        "STALE HERO FOLD: PASS"
    )
    print(
        "HERO REMAINS ACTIVE ON TURN: PASS"
    )
    print(
        "NO PREMATURE HAND COMPLETE: PASS"
    )
    print(
        "V0.17 HERO REAPPEARANCE / "
        "TURN BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
