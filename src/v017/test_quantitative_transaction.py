from src.v017.quantitative_transaction import (
    filter_common_mode_quantitative_events,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


def observation(
    seat,
    frame,
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
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
    }


def main():
    # Exact Live #1 class:
    # five correlated 0.10 movements in one frame.
    rows = tuple(
        observation(
            seat,
            79,
            prior,
            value,
        )
        for seat, prior, value in (
            ("seat_top", 30.25, 30.15),
            (
                "seat_upper_right",
                19.17,
                19.07,
            ),
            (
                "seat_mid_right",
                31.27,
                31.17,
            ),
            (
                "seat_lower_right",
                17.46,
                17.36,
            ),
            (
                "seat_lower_left",
                5.28,
                5.18,
            ),
        )
    )

    eligible, rejected = (
        filter_common_mode_quantitative_events(
            rows
        )
    )

    print(
        "live1 eligible =",
        [x["seat"] for x in eligible],
    )
    print(
        "live1 rejected =",
        [x["seat"] for x in rejected],
    )

    assert eligible == ()
    assert len(rejected) == 5

    # Exact Live #2 frame 24 class:
    # only two correlated seats. Current production rule intentionally
    # does NOT reject this. We preserve that behavior here so the lab
    # can reproduce the remaining defect instead of hiding it.
    rows = (
        observation(
            "seat_mid_right",
            24,
            31.01,
            30.91,
        ),
        observation(
            "hero",
            24,
            18.30,
            18.20,
        ),
    )

    eligible, rejected = (
        filter_common_mode_quantitative_events(
            rows
        )
    )

    print(
        "live2-frame24 eligible =",
        [x["seat"] for x in eligible],
    )
    print(
        "live2-frame24 rejected =",
        [x["seat"] for x in rejected],
    )

    assert len(eligible) == 2
    assert rejected == ()

    # Settlement semantics remain independently two-frame.
    gate = StackSettlementGate()

    first = gate.observe(
        observation(
            "hero",
            24,
            18.30,
            18.20,
        ),
        phase="PREFLOP",
        has_commitment_evidence=False,
    )

    assert first is None
    assert "hero" in gate.pending

    second = gate.observe(
        observation(
            "hero",
            25,
            18.30,
            18.20,
        ),
        phase="PREFLOP",
        has_commitment_evidence=False,
    )

    assert second is not None
    assert abs(second.delta_bb - 0.10) < 0.001

    print()
    print(
        "SHARED QUANTITATIVE TRANSACTION "
        "CURRENT LIVE BEHAVIOR: PASS"
    )


if __name__ == "__main__":
    main()
