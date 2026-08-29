"""
Regression contract for zero-OCR clean postflop boundaries.

The state-machine-owned betting status must expose enough authoritative
information for the coordinator to know that retrospective boundary stack OCR
is unnecessary.

Safety contract:
- unopened FLOP/TURN with zero price and no quantitative/physical ownership
  may advertise skip;
- open betting may not;
- a current price may not;
- an aggressor may not;
- unresolved stack candidates may not;
- provisional bets may not;
- commitment candidates may not.
"""

import inspect

import src.api.api_event_state_machine as sm


def main():
    helper = getattr(
        sm,
        "boundary_can_resolve_passively_without_stack_ocr",
        None,
    )

    assert helper is not None

    clean = helper(
        street="TURN",
        betting_open=False,
        current_price=0.0,
        last_aggressor=None,
        unresolved_candidates=[],
        provisional_bets=[],
        commitment_candidates=[],
    )

    assert clean is True

    blocked_cases = [
        dict(
            betting_open=True,
            current_price=0.0,
            last_aggressor=None,
            unresolved_candidates=[],
            provisional_bets=[],
            commitment_candidates=[],
        ),
        dict(
            betting_open=False,
            current_price=1.0,
            last_aggressor=None,
            unresolved_candidates=[],
            provisional_bets=[],
            commitment_candidates=[],
        ),
        dict(
            betting_open=False,
            current_price=0.0,
            last_aggressor="hero",
            unresolved_candidates=[],
            provisional_bets=[],
            commitment_candidates=[],
        ),
        dict(
            betting_open=False,
            current_price=0.0,
            last_aggressor=None,
            unresolved_candidates=["hero"],
            provisional_bets=[],
            commitment_candidates=[],
        ),
        dict(
            betting_open=False,
            current_price=0.0,
            last_aggressor=None,
            unresolved_candidates=[],
            provisional_bets=["hero"],
            commitment_candidates=[],
        ),
        dict(
            betting_open=False,
            current_price=0.0,
            last_aggressor=None,
            unresolved_candidates=[],
            provisional_bets=[],
            commitment_candidates=["hero"],
        ),
    ]

    for case in blocked_cases:
        allowed = helper(
            street="TURN",
            **case,
        )
        assert allowed is False, case

    source = inspect.getsource(
        sm.write_betting_round_status
    )

    required_status_signal = (
        "boundary_can_skip_stack_ocr"
    )

    print("===== PURE PREDICATE =====")
    print("clean unopened TURN:", clean)
    print("blocked safety cases:", len(blocked_cases))

    print()
    print("===== STATUS CONTRACT =====")
    print(
        "boundary_can_skip_stack_ocr published:",
        required_status_signal in source,
    )

    assert required_status_signal in source, (
        "RED: authoritative betting-round status does not yet publish "
        "whether this clean postflop boundary can skip retrospective "
        "stack OCR"
    )

    print()
    print(
        "PASS boundary status exposes conservative zero-OCR "
        "postflop closure authority"
    )


if __name__ == "__main__":
    main()
