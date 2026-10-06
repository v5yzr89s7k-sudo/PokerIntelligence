"""
Regression for async board identity outrunning a retained physical
street boundary.

A valid FLOP identity may complete while semantic chronology is still
PREFLOP because the physical FLOP boundary is retained behind unresolved
prior-street action. Identity must wait; it must never be attached to
HandEngine before FLOP becomes active.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
import src.v017.run_live_observer as live


PLAYERS = [
    {
        "seat": "villain",
        "position": "UTG",
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
        "is_hero": True,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["villain", "hero"],
        small_blind_seat="hero",
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
        quantitative_seats=["villain"],
        hero_seat="hero",
        hand_id="board-identity-retained-boundary",
    )

    boundary = {
        "frame": 46,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
        "previous_board_count": 0,
    }

    # Prior street is deliberately unresolved. Therefore the physical
    # FLOP must be retained and semantic chronology remains PREFLOP.
    admitted = observer.admit_street_boundary(
        boundary,
        action_order=["villain", "hero"],
        board=None,
        complete_pending=False,
    )

    assert not admitted
    assert observer.hand.street == "PREFLOP"
    assert observer.hand.board == []
    assert len(
        observer.pending_street_boundaries
    ) == 1

    completed = {
        "request": {
            "boundary_event": boundary,
            "expected_count": 3,
        },
        "board": ["8s", "Tc", "7d"],
        "error": None,
    }

    # LIVE FAILURE CONTRACT:
    #
    # The board reader has completed, but FLOP chronology is not yet
    # active. Production must retain/defer identity instead of calling
    # HandEngine.observe_board_identity() on PREFLOP.
    state = live.FrameTransactionState()

    result = live.finalize_async_board_identity_result(
        observer,
        state,
        completed,
        publication_frame=47,
    )

    assert result["applied"] is False
    assert result["deferred"] is True

    assert (
        state.pending_board_identity_result
        is completed
    )

    assert observer.hand.street == "PREFLOP"
    assert observer.hand.board == []

    # The physical chronology can later close independently.
    observer.admit_card_disappearance(
        "villain",
        frame_id=48,
        physical_type="OPPONENT_CARDS_DISAPPEARED_PHYSICAL",
    )
    observer.admit_card_disappearance(
        "hero",
        frame_id=49,
        physical_type="HERO_CARDS_DISAPPEARED_PHYSICAL",
    )

    observer.reconcile_pending_street_boundaries()

    assert observer.hand.street == "FLOP"

    result = live.finalize_async_board_identity_result(
        observer,
        state,
        state.pending_board_identity_result,
        publication_frame=49,
    )

    assert result["applied"] is True
    assert state.pending_board_identity_result is None
    assert observer.hand.board == [
        "8s",
        "Tc",
        "7d",
    ]

    print(
        "EARLY FLOP IDENTITY ATTACHED TO PREFLOP: NO"
    )
    print(
        "BOARD IDENTITY WAITS FOR RETAINED "
        "STREET BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
