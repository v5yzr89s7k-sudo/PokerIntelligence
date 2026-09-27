from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


def observation(
    frame,
    *,
    prior,
    value,
):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "seat_top",
        "prior": float(prior),
        "resolved": True,
        "resolved_value": float(value),
        "confidence": 0.95,
        "votes": 2,
        "mode": "native_green_fast",
        "candidates": ((float(value), 2),),
    }


def retire_stale_candidate(
    gate,
    *,
    seat,
    trusted_baseline,
):
    pending = gate.pending.get(seat)

    if (
        pending is not None
        and abs(
            float(pending.value)
            - float(trusted_baseline)
        ) <= 0.01
    ):
        gate.clear_seat(seat)
        return True

    return False


def main():
    gate = StackSettlementGate()

    first = observation(
        209,
        prior=9.71,
        value=8.71,
    )

    settled = gate.observe(
        first,
        phase="PREFLOP",
        has_commitment_evidence=True,
    )

    assert settled is None
    assert "seat_top" in gate.pending

    print(
        "candidate_frame_209=",
        gate.pending["seat_top"],
    )

    retired = retire_stale_candidate(
        gate,
        seat="seat_top",
        trusted_baseline=8.71,
    )

    assert retired is True
    assert "seat_top" not in gate.pending

    print(
        "STALE SETTLEMENT CANDIDATE RETIREMENT: PASS"
    )


if __name__ == "__main__":
    main()
