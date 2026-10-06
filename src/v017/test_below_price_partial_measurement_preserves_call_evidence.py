"""
Regression: a partial below-price stack measurement must not destroy
the physical baseline needed to recognize the completed call.
"""

from src.v017.frame_hand_observer import FrameHandObserver


def main():
    observer = FrameHandObserver(
        players=[
            {
                "seat": "villain",
                "position": "UTG",
                "name": "Villain",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
            {
                "seat": "hero",
                "position": "BTN",
                "name": "Hero",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
        ],
        action_order=["villain", "hero"],
        small_blind_seat="villain",
        big_blind_seat="hero",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "villain": 50.0,
            "hero": 50.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=["villain", "hero"],
        hero_seat="hero",
        hand_id="partial-call-evidence",
    )

    # Villain is SB and already owns 0.5 BB preflop.
    # A further 3.12 BB physical commitment establishes
    # an authoritative raise-to price of 3.62 BB.
    first = observer.admit_quantitative_observation({
        "frame": 10,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "villain",
        "resolved": True,
        "resolved_value": 46.88,
    })

    assert first
    assert abs(
        observer.hand.current_price_bb - 3.62
    ) < 0.02
    assert observer.hand.next_actor == "hero"

    # Hero action completion owns a bounded follow-up opportunity.
    # Only this ownership permits a below-price intermediate reading
    # to preserve the older cumulative physical baseline.
    observer.quantitative_retry_pending["hero"] = {
        "attempts": 1,
        "first_frame": 11,
        "last_frame": 11,
        "commitment_seen": True,
        "reason": "hero_action_completion",
    }

    # First Hero measurement sees only part of the physical movement.
    partial = observer.admit_quantitative_observation({
        "frame": 11,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "resolved": True,
        "resolved_value": 48.0,
    })

    assert not partial

    # Later measurement sees the completed call.
    completed = observer.admit_quantitative_observation({
        "frame": 12,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "resolved": True,
        "resolved_value": 47.38,
    })

    actions = observer.hand.semantic_actions()

    hero_calls = [
        row
        for row in actions
        if row.get("seat") == "hero"
        and row.get("action") == "CALL"
    ]

    assert completed, (
        "RED: completed Hero call was lost after partial "
        "below-price measurement advanced physical baseline"
    )

    assert len(hero_calls) == 1, hero_calls

    print("PARTIAL BELOW-PRICE EVIDENCE DESTROYED: NO")
    print("COMPLETED HERO CALL ADMITTED: PASS")


if __name__ == "__main__":
    main()
