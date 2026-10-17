"""
Regression for live Hand 17.

A player's betting action may already have been consumed before the
physical zero-stack measurement settles.

If that later measurement has independent all-in authority, it must
persist player.all_in=True WITHOUT creating another betting action.

Other live players with chips remain normally actionable.
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "short",
        "position": "LJ",
        "name": "Short",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "deep",
        "position": "SB",
        "name": "Deep",
        "stack_bb": 60.0,
        "dealt_in": True,
    },
    {
        "seat": "other",
        "position": "BB",
        "name": "Other",
        "stack_bb": 100.0,
        "dealt_in": True,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["short", "deep", "other"],
        small_blind_seat="deep",
        big_blind_seat="other",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "short": 7.0,
            "deep": 60.0,
            "other": 100.0,
        },
        opponent_seats=["short", "deep", "other"],
        quantitative_seats=["short", "deep", "other"],
        hero_seat="other",
        hand_id="consumed-zero-stack-allin",
    )

    # Model the live condition:
    # Short's semantic betting action has already been consumed.
    observer.hand.pending_to_act = [
        "deep",
        "other",
    ]

    actions_before = tuple(
        observer.hand.semantic_actions()
    )

    observation = {
        "frame": 203,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "short",
        "prior": 7.0,
        "reader_value": 0.0,
        "resolved": True,
        "resolved_value": 0.0,
        "candidates": ((0.0, 1),),
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": 7.0,
    }

    admitted = observer.admit_quantitative_observation(
        observation,
        all_in_confirmed=True,
    )

    # No duplicate betting action.
    assert admitted == ()
    assert tuple(
        observer.hand.semantic_actions()
    ) == actions_before

    # RED CONTRACT:
    assert observer.hand.players["short"].all_in is True, (
        "RED: confirmed zero-stack all-in state was lost "
        "because the player's betting action was already consumed"
    )

    # Multiway safeguard: this does NOT close the hand.
    assert observer.hand.next_actor == "deep"
    assert observer.hand.pending_to_act == [
        "deep",
        "other",
    ]
    assert observer.hand.hand_complete is False

    # Showdown/runout card disappearance from Short must therefore
    # never become a future FOLD.
    observer.retain_card_disappearance(
        "short",
        frame_id=208,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    observer.reconcile_pending_card_disappearances()

    assert observer.hand.players["short"].folded is False

    print(
        "CONSUMED ACTOR ZERO-STACK -> PERSISTENT ALL-IN: PASS"
    )
    print(
        "NO DUPLICATE ACTION: PASS"
    )
    print(
        "MULTIWAY ACTIONABILITY PRESERVED: PASS"
    )


if __name__ == "__main__":
    main()
