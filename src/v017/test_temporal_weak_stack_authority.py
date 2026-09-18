from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


def observation(
    *,
    frame,
    seat,
    prior,
    value,
):
    return {
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "frame": frame,
        "resolved": True,
        "resolved_value": value,
        "prior": prior,

        # Exact July22 BB call reader contract.
        "confidence": 0.5,
        "votes": 1,
        "mode": "segmentation_disagreement",
    }


def main():
    # --------------------------------------------------------
    # Exact July22 BB preflop call:
    #
    # frame 51: 48.57 -> 47.57
    # frame 52: 48.57 -> 47.57
    #
    # The two independent physical frames agree exactly.
    # Temporal agreement must be capable of establishing
    # measurement authority even though either single OCR frame
    # has weak segmentation consensus.
    # --------------------------------------------------------

    gate = StackSettlementGate()

    first = gate.observe(
        observation(
            frame=51,
            seat="seat_lower_left",
            prior=48.57,
            value=47.57,
        ),
        phase="PREFLOP",
        has_commitment_evidence=False,
        all_in_confirmed=False,
    )

    print(
        "after frame51 pending =",
        gate.pending,
    )

    assert first is None

    assert "seat_lower_left" in gate.pending, (
        "MISSING ARCHITECTURE: weak but resolved "
        "physical stack observation cannot enter "
        "temporal confirmation epoch"
    )

    second = gate.observe(
        observation(
            frame=52,
            seat="seat_lower_left",
            prior=48.57,
            value=47.57,
        ),
        phase="PREFLOP",
        has_commitment_evidence=False,
        all_in_confirmed=False,
    )

    print(
        "after frame52 pending =",
        gate.pending,
    )
    print(
        "settled =",
        second,
    )

    assert second is not None, (
        "MISSING TEMPORAL AUTHORITY: two independent "
        "resolved frames agreeing on 47.57 did not "
        "establish settlement"
    )

    assert second.seat == "seat_lower_left"
    assert abs(second.prior - 48.57) < 0.001
    assert abs(second.value - 47.57) < 0.001
    assert abs(second.delta_bb - 1.0) < 0.001

    print()
    print(
        "V0.17 TEMPORAL WEAK STACK AUTHORITY: PASS"
    )


if __name__ == "__main__":
    main()
