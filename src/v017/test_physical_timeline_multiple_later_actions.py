"""
V0.17 multi-event physical chronology contract.

Several objectively proven later observations must remain ordered by
their physical frame while the canonical HandEngine frontier remains
blocked on an earlier actor.

next_actor may constrain canonical mutation.
It may not constrain what the observer physically knows.
"""

from src.v017.frame_hand_observer import FrameHandObserver
from src.v017.test_blocked_quantitative_evidence_retention import (
    PLAYERS,
    quantitative,
)


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
        hand_id="multiple-later-actions",
    )


def main():
    observer = build_observer()

    assert observer.hand.next_actor == "utg"

    before_actions = list(
        observer.hand.semantic_actions()
    )

    # Deliberately submit out of frame order.
    #
    # The resolver must establish physical chronology from original
    # frame identity rather than queue insertion order.

    observer.admit_card_disappearance(
        "sb",
        frame_id=12,
        physical_type=
            "OPPONENT_CARDS_DISAPPEARED",
    )

    observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    observer.admit_quantitative_observation(
        quantitative(
            14,
            "bb",
            38.0,
        )
    )

    # UTG still owns canonical authority.
    assert observer.hand.next_actor == "utg"

    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    state = (
        observer
        .resolve_physical_evidence_timeline()
    )

    assert state["canonical_next_actor"] == "utg"
    assert state["canonical_blocked"] is True

    chronology = list(
        state["physical_chronology"]
    )

    print("physical_chronology =", chronology)

    assert len(chronology) == 3, chronology

    assert [
        row["frame"]
        for row in chronology
    ] == [
        10,
        12,
        14,
    ], chronology

    hero = chronology[0]
    sb = chronology[1]
    bb = chronology[2]

    assert hero["seat"] == "hero"
    assert hero["evidence_type"] == "QUANTITATIVE"
    assert hero["resolved_value"] == 48.0

    assert sb["seat"] == "sb"
    assert (
        sb["evidence_type"]
        == "CARD_DISAPPEARANCE"
    )
    assert sb["physical_action"] == "FOLD"

    assert bb["seat"] == "bb"
    assert bb["evidence_type"] == "QUANTITATIVE"
    assert bb["resolved_value"] == 38.0

    for row in chronology:
        assert row["physical_status"] == "PROVEN"
        assert (
            row["canonical_status"]
            == "BLOCKED_BY_PREDECESSOR"
        )

    # No event may have escaped into canonical semantics.
    assert observer.hand.next_actor == "utg"

    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    print("THREE LATER OBSERVATIONS PRESERVED: PASS")
    print("PHYSICAL FRAME ORDER PRESERVED: PASS")
    print("INSERTION ORDER IGNORED: PASS")
    print("CANONICAL FRONTIER UNCHANGED: PASS")
    print("UNKNOWN UTG ACTION INVENTED: NO")
    print(
        "V0.17 MULTI-EVENT PHYSICAL TIMELINE: PASS"
    )


if __name__ == "__main__":
    main()
