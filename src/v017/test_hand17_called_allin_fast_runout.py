"""
Hand 17 regression — 2026-10-16 live evidence.

Required lifecycle:

1. First player has already made the large preflop commitment.
2. Its final physical stack transition later settles to zero after
   that betting action was already consumed.
3. Zero-stack authority persists all_in=True without another action.
4. Second player completes the called-all-in betting sequence.
5. Betting becomes closed.
6. Showdown card disappearance cannot become FOLD.
7. Rapid FLOP -> TURN -> RIVER advances with no betting actions.
8. Hand remains contested pending objective winner evidence.
"""

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "lj",
        "position": "LJ",
        "name": "lflopdit77",
        "stack_bb": 49.85,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "Paletokyo",
        "stack_bb": 57.42,
        "dealt_in": True,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["lj", "sb"],
        small_blind_seat="sb",
        big_blind_seat="lj",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "lj": 7.20,
            "sb": 57.42,
        },
        opponent_seats=["lj", "sb"],
        quantitative_seats=["lj", "sb"],
        hero_seat="unused_hero",
        hand_id="live-v017-17-regression",
    )

    hand = observer.hand

    # Reconstruct the authoritative state immediately before frame 203.
    #
    # LJ's 42.65 BB raise has already been consumed semantically.
    # SB is now the authoritative actor.
    lj = hand.players["lj"]
    sb = hand.players["sb"]

    lj.street_commitment_bb = 42.65
    lj.total_contribution_bb = 42.65

    sb.street_commitment_bb = 0.50
    sb.total_contribution_bb = 0.50

    hand.current_price_bb = 42.65
    hand.pot_bb = 43.15
    hand.pending_to_act = ["sb"]

    # Frame 203: LJ's remaining 7.20 physically reaches zero after
    # LJ's prior betting action has already been consumed.
    actions_before_zero = tuple(
        hand.semantic_actions()
    )

    zero = {
        "frame": 203,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "lj",
        "prior": 7.20,
        "reader_value": 0.0,
        "resolved": True,
        "resolved_value": 0.0,
        "candidates": ((0.0, 1),),
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": 7.20,
    }

    assert observer.admit_quantitative_observation(
        zero,
        all_in_confirmed=True,
    ) == ()

    assert tuple(
        hand.semantic_actions()
    ) == actions_before_zero

    assert hand.players["lj"].all_in is True
    assert hand.players["lj"].folded is False

    # SB completes the all-in confrontation.
    #
    # Hand 17 live measurement:
    # SB 57.42 -> 8.07 = 49.35 BB physical commitment.
    sb_commit = {
        "frame": 203,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "sb",
        "prior": 57.42,
        "reader_value": 8.07,
        "resolved": True,
        "resolved_value": 8.07,
        "candidates": ((8.07, 1),),
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": 49.35,
    }

    admitted = observer.admit_quantitative_observation(
        sb_commit,
        all_in_confirmed=False,
    )

    assert admitted
    assert hand.players["lj"].folded is False

    # In the real hand only LJ and SB remain.
    # LJ is all-in; SB has completed the required response.
    assert hand.next_actor is None
    assert hand.pending_to_act == []

    actions_before_disappearance = tuple(
        hand.semantic_actions()
    )

    # Frame 208 showdown transition: both hole-card regions disappear.
    # Neither observation may become a fold once betting is closed.
    assert observer.admit_card_disappearance(
        "lj",
        frame_id=208,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    ) is None

    assert observer.admit_card_disappearance(
        "sb",
        frame_id=208,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    ) is None

    assert observer.pending_card_disappearances == []
    assert hand.players["lj"].folded is False
    assert hand.players["sb"].folded is False

    assert tuple(
        hand.semantic_actions()
    ) == actions_before_disappearance

    # Rapid automatic runout. Card identities are representative;
    # this regression owns chronology, not the historical board ranks.
    hand.start_street(
        "FLOP",
        ["lj", "sb"],
        board=["2c", "7d", "9h"],
    )

    assert hand.street == "FLOP"
    assert hand.next_actor is None

    hand.start_street(
        "TURN",
        ["lj", "sb"],
        board=["2c", "7d", "9h", "Qs"],
    )

    assert hand.street == "TURN"
    assert hand.next_actor is None

    hand.start_street(
        "RIVER",
        ["lj", "sb"],
        board=["2c", "7d", "9h", "Qs", "3c"],
    )

    assert hand.street == "RIVER"
    assert hand.next_actor is None

    # Board runout must not fabricate betting semantics.
    assert tuple(
        hand.semantic_actions()
    ) == actions_before_disappearance

    # No fold-based false completion.
    assert hand.hand_complete is False
    assert hand.completion_reason is None
    assert hand.winner_seats == []

    print(
        "HAND 17 CONSUMED ZERO-STACK ALL-IN: PASS"
    )
    print(
        "HAND 17 SHOWDOWN DISAPPEARANCE != FOLD: PASS"
    )
    print(
        "HAND 17 RAPID FLOP/TURN/RIVER: PASS"
    )
    print(
        "HAND 17 REMAINS CONTESTED FOR WINNER EVIDENCE: PASS"
    )


if __name__ == "__main__":
    main()
