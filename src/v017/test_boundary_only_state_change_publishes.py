"""
Regression: a physical transaction whose authoritative HandEngine state
changes only by street/board/next-actor must still publish.

Publication cannot be gated only by action-count growth.
"""

from unittest.mock import patch
import numpy as np

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    FrameObservationResult,
)
from src.v017.run_live_observer import (
    FrameTransactionState,
    process_frame_transaction,
)


def main():
    observer = FrameHandObserver(
        players=[
            {
                "seat": "hero",
                "position": "CO",
                "name": "Hero",
                "stack_bb": 40.0,
                "dealt_in": True,
            },
            {
                "seat": "bb",
                "position": "BB",
                "name": "BB",
                "stack_bb": 40.0,
                "dealt_in": True,
            },
        ],
        action_order=["hero", "bb"],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 40.0,
            "bb": 40.0,
        },
        opponent_seats=["bb"],
        quantitative_seats=["hero", "bb"],
        hero_seat="hero",
        hand_id="boundary-only-publication",
    )

    # Establish a baseline publication exactly as live bootstrap does.
    observer.publish_authoritative_state("bootstrap")
    before_publications = len(observer.publications)
    before_actions = len(observer.hand.actions)

    # Make BB the unresolved priced actor.
    observer.hand.pending_to_act = ["bb"]
    observer.hand.current_price_bb = 2.0
    observer.hand.players["bb"].street_commitment_bb = 1.0

    # Directly retain an already-authoritative FLOP boundary so frame
    # reconciliation can mutate street/board without adding an action.
    observer._retain_pending_street_boundary(
        {
            "frame": 10,
            "type": "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
            "previous_board_count": 0,
        },
        action_order=["bb", "hero"],
        board=["Qc", "3c", "6c"],
        complete_pending=True,
    )

    state = FrameTransactionState()

    frame = np.zeros(
        (2168, 3456, 3),
        dtype=np.uint8,
    )

    # Isolate this contract from unrelated perception lanes. The retained
    # boundary is the only authoritative mutation under test.
    with patch.object(
        observer,
        "process_frame",
        return_value=FrameObservationResult(
            frame_id=11,
            events=(),
            changed=False,
            text=None,
        ),
    ), patch(
        "src.v017.run_live_observer.reconcile_frame_evidence",
        side_effect=lambda obs: (
            (),
            (),
        ) if not (
            obs.reconcile_pending_street_boundaries()
        ) else (
            (),
            (),
        ),
    ), patch(
        "src.v017.run_live_observer.detect_winner",
        return_value={"visible": False},
    ):
        process_frame_transaction(
            observer,
            frame,
            "/tmp/boundary_only.png",
            11,
            state,
        )

    after_actions = len(observer.hand.actions)
    after_publications = len(observer.publications)

    print("street =", observer.hand.street)
    print("board =", observer.hand.board)
    print(
        "actions_before_after =",
        before_actions,
        after_actions,
    )
    print(
        "publications_before_after =",
        before_publications,
        after_publications,
    )

    assert observer.hand.street == "FLOP"
    assert observer.hand.board == [
        "Qc",
        "3c",
        "6c",
    ]

    assert after_actions == before_actions, (
        "boundary-only contract unexpectedly added action"
    )

    assert after_publications == before_publications + 1, (
        "authoritative boundary-only state change was not published"
    )

    publication = observer.publications[-1]

    assert publication["street"] == "FLOP"
    assert "FLOP: Qc 3c 6c" in publication["text"]

    print("ACTION COUNT CHANGED: NO")
    print("AUTHORITATIVE STATE PUBLISHED: PASS")
    print(
        "V0.17 BOUNDARY-ONLY PUBLICATION: PASS"
    )


if __name__ == "__main__":
    main()
