from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


def unresolved(
    *,
    frame,
    value=0.0,
    candidates=((0.0, 1),),
):
    return {
        "frame": frame,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "seat_mid_right",
        "prior": 22.94,
        "reader_value": None,
        "resolved": True,
        "resolved_value": value,
        "candidates": candidates,
        "confidence": 0.0,
        "votes": 0,
        "mode": "native_fast_unresolved",
        "physical_delta_bb":
            round(22.94 - value, 2),
    }


def main():
    # --------------------------------------------------------
    # 1. Unresolved zero without independent physical all-in
    #    evidence must have NO candidate authority.
    # --------------------------------------------------------

    gate = StackSettlementGate()

    assert gate.observe(
        unresolved(
            frame=25,
        ),
        phase="PREFLOP",
        has_commitment_evidence=False,
        all_in_confirmed=False,
    ) is None

    assert gate.pending == {}

    assert gate.observe(
        unresolved(
            frame=30,
        ),
        phase="PREFLOP",
        has_commitment_evidence=False,
        all_in_confirmed=False,
    ) is None

    assert gate.pending == {}

    print(
        "unresolved zero without all-in evidence: BLOCKED"
    )

    # --------------------------------------------------------
    # 2. Generic commitment evidence is still insufficient.
    # --------------------------------------------------------

    gate = StackSettlementGate()

    assert gate.observe(
        unresolved(
            frame=25,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
        all_in_confirmed=False,
    ) is None

    assert gate.pending == {}

    print(
        "unresolved zero with commitment only: BLOCKED"
    )

    # --------------------------------------------------------
    # 3. A nonzero unresolved read must never inherit this
    #    special authority.
    # --------------------------------------------------------

    gate = StackSettlementGate()

    assert gate.observe(
        unresolved(
            frame=25,
            value=10.0,
            candidates=((10.0, 1),),
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
        all_in_confirmed=True,
    ) is None

    assert gate.pending == {}

    print(
        "unresolved nonzero: BLOCKED"
    )

    # --------------------------------------------------------
    # 4. Even zero requires the exact raw zero candidate shape.
    # --------------------------------------------------------

    gate = StackSettlementGate()

    assert gate.observe(
        unresolved(
            frame=25,
            candidates=((8.0, 1),),
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
        all_in_confirmed=True,
    ) is None

    assert gate.pending == {}

    print(
        "zero without zero candidate: BLOCKED"
    )

    # --------------------------------------------------------
    # 5. One physically confirmed zero creates a candidate,
    #    but cannot settle by itself.
    # --------------------------------------------------------

    gate = StackSettlementGate()

    first = gate.observe(
        unresolved(
            frame=25,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
        all_in_confirmed=True,
    )

    assert first is None
    assert "seat_mid_right" in gate.pending

    candidate = gate.pending[
        "seat_mid_right"
    ]

    assert candidate.value == 0.0
    assert candidate.first_frame == 25

    print(
        "first confirmed zero: CANDIDATE ONLY"
    )

    # Same source frame is not independent evidence.
    duplicate = gate.observe(
        unresolved(
            frame=25,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
        all_in_confirmed=True,
    )

    assert duplicate is None
    assert "seat_mid_right" in gate.pending

    print(
        "same-frame duplicate: BLOCKED"
    )

    # --------------------------------------------------------
    # 6. Independent later physically-confirmed zero settles.
    # --------------------------------------------------------

    settled = gate.observe(
        unresolved(
            frame=30,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
        all_in_confirmed=True,
    )

    assert settled is not None
    assert settled.seat == "seat_mid_right"
    assert abs(settled.prior - 22.94) < 0.001
    assert abs(settled.value) < 0.001
    assert abs(settled.delta_bb - 22.94) < 0.001
    assert gate.pending == {}

    print(
        "later confirmed zero =",
        settled,
    )

    print()
    print(
        "V0.17 PHYSICALLY-CONFIRMED ZERO AUTHORITY: PASS"
    )


if __name__ == "__main__":
    main()
