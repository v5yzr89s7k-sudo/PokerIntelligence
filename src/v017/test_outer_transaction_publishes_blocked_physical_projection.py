"""
V0.17 product RED.

A physical frame that adds independently proven later evidence must
change the live product even when canonical HandEngine state does not
change because next_actor remains unresolved.

The physical transaction remains the sole publication owner.
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


PLAYERS = [
    {
        "seat": "utg",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "HJ",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 40.0,
        "dealt_in": True,
    },
]


def build_observer():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "utg",
            "hero",
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
            "utg": 50.0,
            "hero": 50.0,
            "sb": 20.0,
            "bb": 40.0,
        },
        opponent_seats=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        hero_seat="hero",
        hand_id="outer-live-projection",
    )


def main():
    observer = build_observer()

    assert observer.hand.next_actor == "utg"

    # Bootstrap establishes the existing product publication exactly
    # as production does.
    observer.publish_authoritative_state(
        "bootstrap"
    )

    before_publications = len(
        observer.publications
    )

    before_actions = list(
        observer.hand.semantic_actions()
    )

    frame = np.zeros(
        (2168, 3456, 3),
        dtype=np.uint8,
    )

    # This frame contains objective SB disappearance evidence only.
    #
    # UTG remains unresolved, therefore HandEngine cannot admit SB's
    # fold canonically yet.
    physical_event = {
        "frame": 10,
        "type":
            "OPPONENT_CARDS_DISAPPEARED",
        "seat": "sb",
    }

    state = FrameTransactionState()

    with patch.object(
        observer,
        "process_frame",
        return_value=FrameObservationResult(
            frame_id=10,
            events=(physical_event,),
            changed=True,
            text=None,
        ),
    ), patch(
        "src.v017.run_live_observer.detect_winner",
        return_value={"visible": False},
    ):
        process_frame_transaction(
            observer,
            frame,
            "/tmp/blocked_physical_projection.png",
            10,
            state,
        )

    after_publications = len(
        observer.publications
    )

    # Canonical poker state must remain blocked.
    assert observer.hand.next_actor == "utg"

    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    retained = [
        row
        for row
        in observer.pending_card_disappearances
        if (
            row.get("seat") == "sb"
            and row.get("frame_id") == 10
        )
    ]

    assert len(retained) == 1, retained

    print(
        "canonical_actions_changed =",
        observer.hand.semantic_actions()
        != before_actions,
    )

    print(
        "publications_before_after =",
        before_publications,
        after_publications,
    )

    # PRODUCT REQUIREMENT:
    #
    # Although canonical state did not move, the live product changed
    # because new independently proven physical evidence now exists.
    assert (
        after_publications
        == before_publications + 1
    ), (
        "outer transaction ignored live physical projection "
        "because canonical HandEngine projection did not change"
    )

    publication = observer.publications[-1]

    text = publication["text"]

    assert (
        "PHYSICALLY OBSERVED — CANONICAL ORDER PENDING"
        in text
    ), (
        "publication was created without live physical projection"
    )

    assert "SB folds" in text

    # Absolutely no invented predecessor action.
    assert "UTG folds" not in text
    assert "UTG calls" not in text
    assert "UTG raises" not in text

    print("CANONICAL STATE CHANGED: NO")
    print("BLOCKED PHYSICAL EVIDENCE PUBLISHED: PASS")
    print("UNKNOWN UTG ACTION INVENTED: NO")
    print(
        "V0.17 OUTER LIVE PROJECTION PUBLICATION: PASS"
    )


if __name__ == "__main__":
    main()
