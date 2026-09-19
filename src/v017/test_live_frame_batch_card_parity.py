"""
V0.17 live-runner frame-batch card ownership contract.

The live runner must preserve same-frame card disappearance before
semantic admission so later quantitative evidence can establish the
correct chronology.

This test exercises the production live-runner helpers without screen
capture or ACR.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
from src.v017.run_live_observer import (
    retain_frame_card_disappearances,
    reconcile_frame_evidence,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "CO",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]


def quantitative():
    return {
        "frame": 19,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "resolved": True,
        "resolved_value": 46.88,
    }


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
        hand_id="live-frame-batch-parity",
    )

    # Close preflop.
    assert (
        observer.hand.observe_stack_commitment(
            "hero",
            0.5,
        )
        == "CALL"
    )
    assert (
        observer.hand.observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )

    observer.hand.start_street(
        "FLOP",
        [
            "bb",
            "hero",
        ],
        board=[
            "Jd",
            "9s",
            "Tc",
        ],
    )

    observer.trusted_stacks["hero"] = 49.0
    observer.trusted_stacks["bb"] = 49.0

    return observer


def main():
    observer = build_observer()

    events = (
        {
            "frame": 19,
            "type":
                "OPPONENT_CARDS_DISAPPEARED",
            "seat": "bb",
        },
        quantitative(),
    )

    retained = (
        retain_frame_card_disappearances(
            observer,
            events,
            frame_id=19,
        )
    )

    assert len(retained) == 1
    assert observer.hand.next_actor == "bb"
    assert (
        len(
            observer.pending_card_disappearances
        )
        == 1
    )

    # Same-frame later-seat quantitative evidence gets authority before
    # the retained card disappearance.
    admitted = (
        observer
        .admit_quantitative_observation(
            quantitative()
        )
    )

    assert admitted

    card_rows, quantitative_rows = (
        reconcile_frame_evidence(
            observer
        )
    )

    # Quantitative admission itself performs the retained-card catch-up,
    # so the explicit end-of-frame drain may already be empty.
    assert card_rows == ()
    assert quantitative_rows == ()

    actions = [
        (
            row["seat"],
            row["action"],
            row["amount_bb"],
            row["raise_to_bb"],
        )
        for row
        in observer.hand.semantic_actions()
        if row["street"] == "FLOP"
    ]

    print(
        "observed flop actions =",
        actions,
    )

    assert actions == [
        (
            "bb",
            "CHECK",
            None,
            None,
        ),
        (
            "hero",
            "BET",
            2.12,
            None,
        ),
        (
            "bb",
            "FOLD",
            None,
            None,
        ),
    ], actions

    assert (
        observer.pending_card_disappearances
        == []
    )

    assert observer.hand.hand_complete
    assert observer.hand.winner_seats == [
        "hero"
    ]

    print()
    print(
        "LIVE FRAME RETAINS CARD FIRST: PASS"
    )
    print(
        "QUANTITATIVE CHRONOLOGY FIRST: PASS"
    )
    print(
        "CHECK -> BET -> FOLD: PASS"
    )
    print(
        "RAW EVENT ORDER OWNS SEMANTICS: NO"
    )
    print()
    print(
        "V0.17 LIVE FRAME-BATCH CARD PARITY: PASS"
    )


if __name__ == "__main__":
    main()
