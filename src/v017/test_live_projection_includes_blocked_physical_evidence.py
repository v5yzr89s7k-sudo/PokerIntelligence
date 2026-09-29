"""
V0.17 live projection contract.

When canonical chronology is blocked by next_actor, independently
proven later physical evidence must still be visible in the live
product.

The projection must:
- preserve canonical HandEngine output,
- clearly separate non-canonical physical observations,
- show proven folds as folds,
- show quantitative evidence as stack observations only,
- never fabricate CALL/BET/RAISE from blocked quantitative evidence.
"""

from src.v017.frame_hand_observer import FrameHandObserver
from src.v017.current_hand_renderer import render_current_hand
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
        hand_id="blocked-live-projection",
    )


def main():
    observer = build_observer()

    assert observer.hand.next_actor == "utg"

    before_actions = list(
        observer.hand.semantic_actions()
    )

    observer.admit_quantitative_observation(
        quantitative(
            10,
            "hero",
            48.0,
        )
    )

    observer.admit_card_disappearance(
        "sb",
        frame_id=12,
        physical_type=
            "OPPONENT_CARDS_DISAPPEARED",
    )

    state = (
        observer
        .resolve_physical_evidence_timeline()
    )

    # This is the target presentation boundary.
    assert hasattr(
        observer,
        "render_live_projection",
    ), (
        "MISSING ARCHITECTURE: live projection cannot expose "
        "proven physical evidence beyond canonical next_actor"
    )

    text = observer.render_live_projection()

    print(text)

    assert (
        "PHYSICALLY OBSERVED — CANONICAL ORDER PENDING"
        in text
    )

    # Proven fold identity is safe to expose.
    assert "SB folds" in text

    # Quantitative observation is physically known but poker
    # semantics are not yet safe because UTG remains unresolved.
    assert "Hero stack observed at 48" in text

    pending_section = text.split(
        "PHYSICALLY OBSERVED — CANONICAL ORDER PENDING",
        1,
    )[1]

    # No blocked quantitative evidence may be upgraded into poker
    # semantics prematurely.
    forbidden = (
        "Hero calls",
        "Hero bets",
        "Hero raises",
        "Hero checks",
    )

    for token in forbidden:
        assert token not in pending_section, (
            "blocked quantitative evidence was given "
            "unproven poker semantics"
        )

    # Canonical engine remains untouched.
    assert observer.hand.next_actor == "utg"

    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    print()
    print("BLOCKED FOLD VISIBLE LIVE: PASS")
    print("BLOCKED STACK OBSERVATION VISIBLE LIVE: PASS")
    print("UNPROVEN POKER ACTION INVENTED: NO")
    print("HAND ENGINE MUTATED: NO")
    print(
        "V0.17 LIVE TWO-FRONTIER PROJECTION: PASS"
    )


if __name__ == "__main__":
    main()
