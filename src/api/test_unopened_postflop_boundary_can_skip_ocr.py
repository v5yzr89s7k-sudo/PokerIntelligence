"""
Contract for eliminating unnecessary boundary OCR.

A confirmed next-street board may close an unopened postflop street
without boundary stack OCR when all remaining obligations are passive
and there is no surviving quantitative or commitment ownership.

This must NOT apply when:
- street is PREFLOP;
- betting is open;
- unresolved stack candidates exist;
- provisional bets exist;
- physical commitment candidates exist.
"""

import src.api.api_event_state_machine as sm


def check(
    *,
    street,
    betting_open=False,
    current_price=0.0,
    last_aggressor=None,
    unresolved_candidates=None,
    provisional_bets=None,
    commitment_candidates=None,
):
    helper = getattr(
        sm,
        "boundary_can_resolve_passively_without_stack_ocr",
        None,
    )

    assert helper is not None, (
        "RED: state machine has no explicit contract for "
        "skipping redundant boundary OCR on an unopened "
        "postflop street"
    )

    return helper(
        street=street,
        betting_open=betting_open,
        current_price=current_price,
        last_aggressor=last_aggressor,
        unresolved_candidates=set(
            unresolved_candidates or []
        ),
        provisional_bets=set(
            provisional_bets or []
        ),
        commitment_candidates=set(
            commitment_candidates or []
        ),
    )


def main():

    print("===== CLEAN TURN =====")

    clean_turn = check(
        street="TURN",
    )

    print("clean TURN:", clean_turn)

    assert clean_turn is True, (
        "RED: clean unopened TURN still requires "
        "boundary stack OCR"
    )

    print()
    print("===== CLEAN FLOP =====")

    clean_flop = check(
        street="FLOP",
    )

    print("clean FLOP:", clean_flop)

    assert clean_flop is True

    print()
    print("===== PREFLOP MUST NOT SKIP =====")

    assert check(
        street="PREFLOP",
    ) is False

    print("PREFLOP protected")

    print()
    print("===== OPEN BETTING MUST NOT SKIP =====")

    assert check(
        street="TURN",
        betting_open=True,
    ) is False

    print("open betting protected")

    print()
    print("===== HISTORICAL AGGRESSION MUST NOT SKIP =====")

    assert check(
        street="TURN",
        current_price=6.75,
        last_aggressor="seat_lower_left",
    ) is False

    print("historical aggression protected")

    print()
    print("===== AGGRESSOR IDENTITY ALONE MUST NOT SKIP =====")

    assert check(
        street="TURN",
        last_aggressor="seat_lower_left",
    ) is False

    print("aggressor identity protected")

    print()
    print("===== QUANTITATIVE CANDIDATE MUST NOT SKIP =====")

    assert check(
        street="TURN",
        unresolved_candidates={"hero"},
    ) is False

    print("quantitative candidate protected")

    print()
    print("===== PROVISIONAL BET MUST NOT SKIP =====")

    assert check(
        street="TURN",
        provisional_bets={"hero"},
    ) is False

    print("provisional bet protected")

    print()
    print("===== COMMITMENT EVIDENCE MUST NOT SKIP =====")

    assert check(
        street="TURN",
        commitment_candidates={"seat_lower_left"},
    ) is False

    print("commitment candidate protected")

    print()
    print(
        "PASS passive postflop boundary OCR-skip contract"
    )


if __name__ == "__main__":
    main()
