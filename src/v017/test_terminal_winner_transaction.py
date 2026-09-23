"""
V0.17 terminal WINNER transaction regression.

Contract:

    no WINNER
        -> no terminal semantic mutation

    authentic WINNER
        -> FrameHandObserver terminal boundary
        -> zero-price pending river actors CHECK
        -> publication
        -> existing HAND_COMPLETE gate

Poker semantics remain owned by FrameHandObserver / HandEngine.
"""

from pathlib import Path

import cv2

from src.v017.frame_hand_observer import (
    FrameHandObserver,
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
    },
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 50.0,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
    },
]


def build_river():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "utg",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={},
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id=
            "terminal-winner-transaction",
    )

    hand = observer.hand

    assert (
        hand.observe_stack_commitment(
            "utg",
            1.0,
        )
        == "CALL"
    )

    assert (
        hand.observe_stack_commitment(
            "hero",
            0.5,
        )
        == "CALL"
    )

    assert (
        hand.observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )

    hand.start_street(
        "FLOP",
        [
            "utg",
            "hero",
            "bb",
        ],
        board=[
            "4d",
            "Qs",
            "Ah",
        ],
    )

    for seat in (
        "utg",
        "hero",
        "bb",
    ):
        assert (
            hand.observe_no_commitment(
                seat
            )
            == "CHECK"
        )

    hand.start_street(
        "TURN",
        [
            "utg",
            "hero",
            "bb",
        ],
        board=[
            "4d",
            "Qs",
            "Ah",
            "8s",
        ],
    )

    for seat in (
        "utg",
        "hero",
        "bb",
    ):
        assert (
            hand.observe_no_commitment(
                seat
            )
            == "CHECK"
        )

    hand.start_street(
        "RIVER",
        [
            "utg",
            "hero",
            "bb",
        ],
        board=[
            "4d",
            "Qs",
            "Ah",
            "8s",
            "3c",
        ],
    )

    return observer


def main():
    root = Path(
        "runtime/pixel_lab/observer_input/"
        "controlled_hand_2826921615"
    )

    frame35 = cv2.imread(
        str(
            root
            / "frame_0035.png"
        )
    )

    frame36 = cv2.imread(
        str(
            root
            / "frame_0036.png"
        )
    )

    assert frame35 is not None
    assert frame36 is not None

    observer = build_river()

    state = FrameTransactionState()

    before = len(
        observer.hand.actions
    )

    tx35 = process_frame_transaction(
        observer,
        frame35,
        root / "frame_0035.png",
        35,
        state,
    )

    assert tx35.outcome == "CONTINUE"

    assert (
        observer.hand.next_actor
        == "utg"
    )

    assert (
        len(observer.hand.actions)
        == before
    )

    before = len(
        observer.hand.actions
    )

    publications = len(
        observer.publications
    )

    tx36 = process_frame_transaction(
        observer,
        frame36,
        root / "frame_0036.png",
        36,
        state,
    )

    new_actions = (
        observer.hand
        .semantic_actions()[before:]
    )

    assert [
        (
            row["seat"],
            row["action"],
        )
        for row in new_actions
    ] == [
        ("utg", "CHECK"),
        ("hero", "CHECK"),
        ("bb", "CHECK"),
    ]

    assert (
        observer.hand.next_actor
        is None
    )

    assert (
        tx36.outcome
        == "HAND_COMPLETE"
    )

    new_publications = (
        observer.publications[
            publications:
        ]
    )

    assert len(
        new_publications
    ) == 1

    assert (
        new_publications[0]["frame"]
        == 36
    )

    print(
        "FRAME 35 WINNER NEGATIVE: PASS"
    )

    print(
        "FRAME 36 TERMINAL CHECK CHAIN: PASS"
    )

    print(
        "FRAME 36 PUBLICATION: PASS"
    )

    print(
        "EXISTING HAND_COMPLETE GATE: PASS"
    )

    print(
        "V0.17 TERMINAL WINNER TRANSACTION: PASS"
    )


if __name__ == "__main__":
    main()
