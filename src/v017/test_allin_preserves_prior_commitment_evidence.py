"""
Regression for live short-all-in authority.

A seat may physically commit chips, establishing independent
bet-region evidence, and then have that region clear before the
zero-stack quantitative observation reaches settlement.

Bounded quantitative ownership already preserves commitment_seen.
The settlement bridge must not forget that prior physical evidence
merely because confirmed_bet_regions is empty on the zero frame.
"""

from src.v017.frame_hand_observer import FrameHandObserver
from src.v017.stack_settlement_gate import StackSettlementGate
from src.v017.quantitative_transaction import process_quantitative_frame


PLAYERS = [
    {
        "seat": "short",
        "position": "BB",
        "name": "Short",
        "stack_bb": 17.54,
    },
    {
        "seat": "raiser",
        "position": "BTN",
        "name": "Raiser",
        "stack_bb": 80.0,
    },
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 50.0,
        "is_hero": True,
    },
]


def observation(frame):
    return {
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "short",
        "frame": frame,
        "resolved": True,
        "resolved_value": 0.0,
        "prior": 17.54,
        "confidence": 0.8,
        "votes": 1,
        "mode": "native_green_fast",
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "raiser",
            "hero",
            "short",
        ],
        small_blind_seat="hero",
        big_blind_seat="short",
        geometry={
            "stack_regions": {},
            "hole_cards": {},
            "hero_cards": {},
            "board": {},
        },
        trusted_stacks={
            "short": 17.54,
            "raiser": 80.0,
            "hero": 50.0,
        },
        opponent_seats=[
            "short",
            "raiser",
        ],
        quantitative_seats=[
            "short",
            "raiser",
            "hero",
        ],
        hero_seat="hero",
        hand_id="prior-commitment-short-allin",
    )

    # Establish an authoritative price above Short's maximum total
    # commitment. Raiser opens to 23.98 BB.
    raised = observer.admit_quantitative_observation({
        "frame": 5,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "raiser",
        "resolved": True,
        "resolved_value": 56.02,
    })

    assert raised
    assert abs(
        observer.hand.current_price_bb - 23.98
    ) < 0.001

    # Hero folds, making Short the canonical next actor.
    observer.admit_card_disappearance(
        "hero",
        frame_id=6,
        physical_type="HERO_CARDS_DISAPPEARED_PHYSICAL",
    )

    assert observer.hand.next_actor == "short"

    # Independent physical chip occupancy was confirmed earlier.
    # Retry ownership preserves that fact.
    observer.quantitative_retry_pending["short"] = {
        "attempts": 1,
        "first_frame": 7,
        "last_frame": 7,
        "commitment_seen": True,
        "reason": "stack_motion",
    }

    # On the later zero-stack frame the visible bet region has
    # already cleared.
    observer.confirmed_bet_regions = set()

    gate = StackSettlementGate()

    first = process_quantitative_frame(
        observer,
        gate,
        (observation(10),),
    )

    assert first.settled == ()
    assert first.admitted == ()

    second = process_quantitative_frame(
        observer,
        gate,
        (observation(11),),
    )

    print("settled =", second.settled)
    print("admitted =", second.admitted)

    assert len(second.settled) == 1, (
        "RED: confirmed zero failed to settle despite "
        "preserved prior commitment evidence"
    )

    assert second.admitted, (
        "RED: short all-in lost prior physical commitment "
        "authority when current bet region cleared"
    )

    actions = observer.hand.semantic_actions()

    short_calls = [
        row
        for row in actions
        if row.get("seat") == "short"
        and row.get("action") == "CALL"
    ]

    assert len(short_calls) == 1, short_calls
    assert observer.hand.players["short"].all_in is True

    print("PRIOR COMMITMENT EVIDENCE PRESERVED: PASS")
    print("SHORT ALL-IN CALL ADMITTED: PASS")
    print("V0.17 ALL-IN TEMPORAL AUTHORITY: PASS")


if __name__ == "__main__":
    main()
