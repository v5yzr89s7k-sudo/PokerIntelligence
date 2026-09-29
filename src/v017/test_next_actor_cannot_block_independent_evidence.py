"""
Architectural RED contract.

Physical evidence already survives a next_actor chronology block.
That is proven elsewhere.

This contract targets the missing layer: an independent chronology
resolver must exist between physical evidence and strict HandEngine
mutation.

HandEngine may retain next_actor as its canonical-order invariant.
FrameHandObserver may not require the current next_actor to produce
new physical evidence before the retained timeline can be reconsidered.
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
        hand_id="independent-evidence-timeline",
    )


def main():
    observer = build_observer()

    assert observer.hand.next_actor == "utg"
    assert observer.hand.current_price_bb == 1.0

    before_actions = list(
        observer.hand.semantic_actions()
    )

    result = observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    assert result == ()

    retained = [
        row
        for row in observer.pending_quantitative_evidence
        if (
            row.get("seat") == "hero"
            and row.get("frame") == 10
        )
    ]

    assert len(retained) == 1, (
        "independent later physical evidence was not retained"
    )

    assert observer.hand.next_actor == "utg"

    assert (
        observer.hand.semantic_actions()
        == before_actions
    ), (
        "strict HandEngine chronology was bypassed"
    )

    print(
        "LATER PHYSICAL EVIDENCE RETAINED: PASS"
    )
    print(
        "STRICT HAND ENGINE CHRONOLOGY: PASS"
    )

    # This is the missing architectural boundary.
    #
    # The resolver is deliberately separate from direct admission.
    # It may use next_actor as a poker-order constraint, but physical
    # evidence ownership/reconsideration must no longer be implemented
    # as "wait until next_actor itself produces another sensor event".
    assert hasattr(
        observer,
        "resolve_physical_evidence_timeline",
    ), (
        "MISSING ARCHITECTURE: no independent physical-evidence "
        "chronology resolver exists; reconciliation remains coupled "
        "directly to next_actor progression"
    )

    print(
        "INDEPENDENT CHRONOLOGY RESOLVER: PRESENT"
    )
    print(
        "V0.17 NEXT_ACTOR OBSERVATION GATE: REMOVED"
    )


if __name__ == "__main__":
    main()
