"""
V0.17 same-frame physical evidence identity contract.

A physical frame may contain multiple independently proven
observations. The resolver must:

1. preserve every unique physical observation,
2. deduplicate identical physical evidence,
3. order same-frame evidence deterministically,
4. never claim the deterministic tie-break is sub-frame chronology,
5. leave HandEngine completely unchanged.
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
        hand_id="same-frame-identity",
    )


def main():
    observer = build_observer()

    assert observer.hand.next_actor == "utg"

    before_actions = list(
        observer.hand.semantic_actions()
    )

    # Deliberately insert quantitative first.
    observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    # Same physical frame, different evidence class.
    observer.admit_card_disappearance(
        "sb",
        frame_id=10,
        physical_type=
            "OPPONENT_CARDS_DISAPPEARED",
    )

    # Duplicate physical card evidence must not create another
    # retained observation.
    observer.admit_card_disappearance(
        "sb",
        frame_id=10,
        physical_type=
            "OPPONENT_CARDS_DISAPPEARED",
    )

    state = (
        observer
        .resolve_physical_evidence_timeline()
    )

    chronology = list(
        state["physical_chronology"]
    )

    print(
        "physical_chronology =",
        chronology,
    )

    assert len(chronology) == 2, chronology

    # Same-frame ordering is deterministic representation only:
    # card disappearance first, quantitative second.
    card = chronology[0]
    quantitative_row = chronology[1]

    assert card["frame"] == 10
    assert card["seat"] == "sb"
    assert (
        card["evidence_type"]
        == "CARD_DISAPPEARANCE"
    )
    assert card["physical_action"] == "FOLD"

    assert quantitative_row["frame"] == 10
    assert quantitative_row["seat"] == "hero"
    assert (
        quantitative_row["evidence_type"]
        == "QUANTITATIVE"
    )
    assert (
        quantitative_row["resolved_value"]
        == 48.0
    )

    # Same-frame evidence must explicitly state that no sub-frame
    # physical ordering has been inferred.
    for row in chronology:
        assert row["same_frame_group"] == 10
        assert (
            row["subframe_order_known"]
            is False
        )

    # Evidence identities must be stable and unique.
    identities = [
        row["evidence_identity"]
        for row in chronology
    ]

    assert len(identities) == 2
    assert len(set(identities)) == 2

    assert (
        card["evidence_identity"]
        == (
            "CARD_DISAPPEARANCE",
            "sb",
            10,
        )
    )

    assert (
        quantitative_row["evidence_identity"]
        == (
            "QUANTITATIVE",
            "hero",
            10,
        )
    )

    # Canonical state remains untouched.
    assert observer.hand.next_actor == "utg"

    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    print("DUPLICATE PHYSICAL EVIDENCE: REMOVED")
    print("SAME-FRAME REPRESENTATION: DETERMINISTIC")
    print("SUB-FRAME ORDER INVENTED: NO")
    print("EVIDENCE IDENTITIES: UNIQUE")
    print("HAND ENGINE MUTATED: NO")
    print(
        "V0.17 SAME-FRAME PHYSICAL TIMELINE: PASS"
    )


if __name__ == "__main__":
    main()
