"""
V0.17 physical timeline classification contract.

Objectively proven evidence beyond the canonical next_actor frontier
must be classified immediately in a separate physical chronology.

This classification does NOT mutate HandEngine and does NOT fabricate
the unresolved predecessor.
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
        hand_id="physical-timeline-classification",
    )


def main():
    observer = build_observer()

    before_actions = list(
        observer.hand.semantic_actions()
    )

    assert observer.hand.next_actor == "utg"

    # Proven later quantitative evidence.
    observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    # Proven still-later fold evidence.
    observer.admit_card_disappearance(
        "sb",
        frame_id=11,
        physical_type=
            "OPPONENT_CARDS_DISAPPEARED",
    )

    # Canonical frontier remains blocked.
    assert observer.hand.next_actor == "utg"

    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    state = (
        observer
        .resolve_physical_evidence_timeline()
    )

    assert state["canonical_blocked"] is True
    assert state["canonical_next_actor"] == "utg"

    assert "physical_chronology" in state, (
        "MISSING ARCHITECTURE: resolver exposes raw evidence "
        "but does not classify the independent physical timeline"
    )

    chronology = state["physical_chronology"]

    assert len(chronology) == 2, chronology

    hero = chronology[0]

    assert hero["frame"] == 10
    assert hero["seat"] == "hero"
    assert hero["evidence_type"] == "QUANTITATIVE"
    assert hero["resolved_value"] == 48.0
    assert hero["physical_status"] == "PROVEN"
    assert (
        hero["canonical_status"]
        == "BLOCKED_BY_PREDECESSOR"
    )

    sb = chronology[1]

    assert sb["frame"] == 11
    assert sb["seat"] == "sb"
    assert (
        sb["evidence_type"]
        == "CARD_DISAPPEARANCE"
    )
    assert sb["physical_action"] == "FOLD"
    assert sb["physical_status"] == "PROVEN"
    assert (
        sb["canonical_status"]
        == "BLOCKED_BY_PREDECESSOR"
    )

    # Resolver remains observation-only.
    assert observer.hand.next_actor == "utg"

    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    print("LATER QUANTITATIVE CLASSIFIED: PASS")
    print("LATER FOLD CLASSIFIED: PASS")
    print("CANONICAL FRONTIER UNCHANGED: PASS")
    print("UNKNOWN UTG ACTION INVENTED: NO")
    print(
        "V0.17 INDEPENDENT PHYSICAL CHRONOLOGY: PASS"
    )


if __name__ == "__main__":
    main()
