"""
Regression for live-v017-1.

Opponent cards disappeared while betting was closed (next_actor=None).
That physical evidence must never survive into a future street and later
be reinterpreted as a FOLD.
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 10.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "villain",
        "position": "BB",
        "name": "Villain",
        "stack_bb": 10.0,
        "dealt_in": True,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["hero", "villain"],
        small_blind_seat="hero",
        big_blind_seat="villain",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 10.0,
            "villain": 10.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="closed-betting-card-disappearance",
    )

    # Legitimately close betting with both players all-in.
    assert observer.hand.observe_stack_commitment(
        "hero",
        9.5,
        all_in_confirmed=True,
    ) == "RAISE"

    assert observer.hand.observe_stack_commitment(
        "villain",
        9.0,
        all_in_confirmed=True,
    ) == "CALL"

    assert observer.hand.next_actor is None
    assert observer.hand.pending_to_act == []

    actions_before = tuple(
        observer.hand.semantic_actions()
    )

    # Live analogue of frame 1647:
    # cards disappear only after betting is already closed.
    result = observer.admit_card_disappearance(
        "villain",
        frame_id=1647,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert result is None

    # Closed-betting disappearance must not acquire future betting
    # ownership.
    assert observer.pending_card_disappearances == [], (
        "RED: card disappearance observed with next_actor=None "
        "was retained for future semantic reinterpretation"
    )

    # Automatic runout.
    observer.hand.start_street(
        "FLOP",
        ["hero", "villain"],
        board=["3s", "3c", "8c"],
    )
    observer.hand.start_street(
        "TURN",
        ["hero", "villain"],
        board=["3s", "3c", "8c", "Qh"],
    )
    observer.hand.start_street(
        "RIVER",
        ["hero", "villain"],
        board=["3s", "3c", "8c", "Qh", "Ks"],
    )

    observer.reconcile_pending_card_disappearances()

    actions_after = tuple(
        observer.hand.semantic_actions()
    )

    assert actions_after == actions_before
    assert observer.hand.hand_complete is False
    assert observer.hand.winner_seats == []

    print(
        "CLOSED-BETTING CARD DISAPPEARANCE "
        "CANNOT BECOME FUTURE FOLD: PASS"
    )


if __name__ == "__main__":
    main()
