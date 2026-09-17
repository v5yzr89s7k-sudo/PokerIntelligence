from src.v017.run_live_observer import (
    filter_common_mode_quantitative_events,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


PRIOR = {
    "seat_top": 30.25,
    "seat_upper_right": 19.17,
    "seat_mid_right": 31.27,
    "seat_lower_right": 17.46,
    "seat_lower_left": 5.28,
}

OBSERVED = {
    "seat_top": 30.15,
    "seat_upper_right": 19.07,
    "seat_mid_right": 31.17,
    "seat_lower_right": 17.36,
    "seat_lower_left": 5.18,
}


def frame_events(frame):
    return tuple(
        {
            "type":
                "STACK_QUANTITATIVE_OBSERVATION",
            "frame": frame,
            "seat": seat,
            "prior": PRIOR[seat],
            "resolved": True,
            "resolved_value": OBSERVED[seat],
            "confidence": 0.80,
            "votes": 1,
            "mode": "native_green_fast",
        }
        for seat in PRIOR
    )


def process_frame(gate, frame):
    eligible, rejected = (
        filter_common_mode_quantitative_events(
            frame_events(frame)
        )
    )

    settlements = []

    for event in eligible:
        settled = gate.observe(
            event,
            phase="PREFLOP",
            has_commitment_evidence=False,
            all_in_confirmed=False,
        )

        if settled is not None:
            settlements.append(settled)

    return eligible, rejected, settlements


def main():
    gate = StackSettlementGate()

    eligible79, rejected79, settled79 = (
        process_frame(gate, 79)
    )

    print(
        "frame79 eligible =",
        [e["seat"] for e in eligible79],
    )
    print(
        "frame79 rejected =",
        [e["seat"] for e in rejected79],
    )
    print(
        "frame79 pending =",
        gate.pending,
    )

    assert eligible79 == ()
    assert len(rejected79) == 5
    assert settled79 == []
    assert gate.pending == {}

    eligible80, rejected80, settled80 = (
        process_frame(gate, 80)
    )

    print(
        "frame80 eligible =",
        [e["seat"] for e in eligible80],
    )
    print(
        "frame80 rejected =",
        [e["seat"] for e in rejected80],
    )
    print(
        "frame80 pending =",
        gate.pending,
    )

    assert eligible80 == ()
    assert len(rejected80) == 5
    assert settled80 == []

    # This is the exact Phase-G safety requirement:
    # persistence across a second frame cannot convert correlated
    # table-wide noise into temporal settlement authority.
    assert gate.pending == {}

    # --------------------------------------------------------
    # Control: a genuine isolated physical commitment still reaches
    # the settlement gate and retains normal two-frame behavior.
    # --------------------------------------------------------

    isolated79 = (
        {
            "type":
                "STACK_QUANTITATIVE_OBSERVATION",
            "frame": 79,
            "seat": "seat_top",
            "prior": 30.25,
            "resolved": True,
            "resolved_value": 28.25,
            "confidence": 0.80,
            "votes": 1,
            "mode": "native_green_fast",
        },
    )

    eligible, rejected = (
        filter_common_mode_quantitative_events(
            isolated79
        )
    )

    assert len(eligible) == 1
    assert rejected == ()

    first = gate.observe(
        eligible[0],
        phase="PREFLOP",
        has_commitment_evidence=True,
    )

    assert first is None
    assert "seat_top" in gate.pending

    isolated80 = (
        {
            **isolated79[0],
            "frame": 80,
        },
    )

    eligible, rejected = (
        filter_common_mode_quantitative_events(
            isolated80
        )
    )

    assert len(eligible) == 1
    assert rejected == ()

    second = gate.observe(
        eligible[0],
        phase="PREFLOP",
        has_commitment_evidence=True,
    )

    assert second is not None
    assert second.seat == "seat_top"
    assert abs(second.delta_bb - 2.0) < 0.001
    assert gate.pending == {}

    print()
    print(
        "PHASE-G COMMON-MODE FRAME 79: "
        "NO SETTLEMENT OWNERSHIP"
    )
    print(
        "PHASE-G COMMON-MODE FRAME 80: "
        "NO TEMPORAL CONFIRMATION"
    )
    print(
        "ISOLATED TWO-FRAME COMMITMENT: "
        "NORMAL SETTLEMENT PRESERVED"
    )
    print()
    print(
        "V0.17 PHASE-G COMMON-MODE "
        "SETTLEMENT TRANSACTION: PASS"
    )


if __name__ == "__main__":
    main()
