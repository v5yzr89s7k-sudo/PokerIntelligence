"""
V0.17 live-projection lifecycle contract.

Physical evidence blocked beyond next_actor is visible immediately in
the pending live projection.

When the predecessor later resolves and retained evidence becomes
canonical, the pending projection must disappear in the same product
state. The action must appear exactly once.
"""

from src.v017.frame_hand_observer import FrameHandObserver


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
        hand_id="pending-to-canonical-lifecycle",
    )


def main():
    observer = build_observer()

    assert observer.hand.next_actor == "utg"

    # Later physical fold arrives first and cannot yet cross canonical
    # chronology.
    blocked = observer.admit_card_disappearance(
        "sb",
        frame_id=10,
        physical_type=
            "OPPONENT_CARDS_DISAPPEARED",
    )

    assert blocked is None

    pending_text = (
        observer.render_live_projection()
    )

    print("===== BLOCKED PRODUCT =====")
    print(pending_text)

    assert (
        "PHYSICALLY OBSERVED — CANONICAL ORDER PENDING"
        in pending_text
    )

    assert "SB folds" in pending_text

    assert len(
        observer.pending_card_disappearances
    ) == 1

    # Resolve UTG and Hero canonically. This advances the legal
    # frontier to SB. Existing reconciliation must then consume the
    # already-retained SB physical fold.
    observer.admit_card_disappearance(
        "utg",
        frame_id=11,
        physical_type=
            "OPPONENT_CARDS_DISAPPEARED",
    )

    assert observer.hand.next_actor == "hero"

    observer.admit_card_disappearance(
        "hero",
        frame_id=12,
        physical_type=
            "HERO_CARDS_DISAPPEARED_PHYSICAL",
    )

    # Reconciliation is expected to release retained SB immediately
    # once the canonical frontier reaches it.
    observer.reconcile_pending_evidence()

    final_text = (
        observer.render_live_projection()
    )

    print()
    print("===== RECONCILED PRODUCT =====")
    print(final_text)

    assert (
        observer.pending_card_disappearances
        == []
    ), observer.pending_card_disappearances

    assert (
        "PHYSICALLY OBSERVED — CANONICAL ORDER PENDING"
        not in final_text
    ), (
        "pending physical section survived after evidence "
        "became canonical"
    )

    # UTG, Hero and SB folds are canonical now.
    assert "UTG folds" in final_text
    assert "HJ (Hero) folds" in final_text
    assert "SB folds" in final_text

    # SB must not exist once canonically plus once as pending.
    assert final_text.count("SB folds") == 1, final_text

    actions = [
        row
        for row in observer.hand.semantic_actions()
        if (
            row.get("seat") == "sb"
            and row.get("action") == "FOLD"
        )
    ]

    assert len(actions) == 1, actions

    print("PENDING SECTION REMOVED: PASS")
    print("SB CANONICAL FOLD COUNT: 1")
    print("DUPLICATE LIVE ACTION: NO")
    print(
        "V0.17 PHYSICAL-TO-CANONICAL LIFECYCLE: PASS"
    )


if __name__ == "__main__":
    main()
