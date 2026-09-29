"""
V0.17 architectural RED.

Physical evidence and canonical poker chronology have separate
frontiers.

A later objectively proven action may exist in the physical timeline
while an earlier canonical action remains unresolved.

The resolver must preserve both facts simultaneously:
- physical knowledge advances;
- HandEngine canonical chronology does not guess.
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
        hand_id="two-frontier-contract",
    )


def main():
    observer = build_observer()

    assert observer.hand.next_actor == "utg"

    before_actions = list(
        observer.hand.semantic_actions()
    )

    # Hero's physical stack change is objectively known even though
    # UTG's canonical action is not.
    emitted = observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    assert emitted == ()

    assert observer.hand.next_actor == "utg"
    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    assert len(
        observer.pending_quantitative_evidence
    ) == 1

    # Missing architectural layer.
    assert hasattr(
        observer,
        "resolve_physical_evidence_timeline",
    ), (
        "MISSING TWO-FRONTIER RESOLVER"
    )

    state = (
        observer
        .resolve_physical_evidence_timeline()
    )

    # Resolver must describe physical knowledge independently from
    # canonical HandEngine advancement.
    assert state["canonical_next_actor"] == "utg"

    assert state["canonical_blocked"] is True

    known = state["known_later_evidence"]

    assert len(known) == 1

    assert known[0]["seat"] == "hero"
    assert known[0]["frame"] == 10
    assert known[0]["resolved_value"] == 48.0

    # Absolutely no fabricated UTG action.
    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    print("PHYSICAL FRONTIER ADVANCED: PASS")
    print("CANONICAL FRONTIER BLOCKED: PASS")
    print("UNKNOWN PREDECESSOR INVENTED: NO")
    print("HAND ENGINE MUTATED: NO")
    print("V0.17 TWO-FRONTIER RESOLVER: PASS")


if __name__ == "__main__":
    main()
