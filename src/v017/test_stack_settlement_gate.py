from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


def obs(
    frame,
    value,
    *,
    prior=20.0,
    confidence=0.98,
    votes=2,
):
    return {
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "frame": frame,
        "seat": "hero",
        "prior": prior,
        "resolved": True,
        "resolved_value": value,
        "confidence": confidence,
        "votes": votes,
        "mode": "agreement_verified",
    }


def main():

    # --------------------------------------------------------
    # One frame cannot settle.
    # --------------------------------------------------------
    gate = StackSettlementGate()

    assert (
        gate.observe(
            obs(10, 17.0),
            phase="PREFLOP",
        )
        is None
    )

    # Same frame is not independent evidence.
    assert (
        gate.observe(
            obs(10, 17.0),
            phase="PREFLOP",
        )
        is None
    )

    # Independent matching frame settles.
    settled = gate.observe(
        obs(11, 17.0),
        phase="PREFLOP",
    )

    assert settled is not None
    assert settled.value == 17.0
    assert settled.delta_bb == 3.0

    # --------------------------------------------------------
    # Weak OCR cannot even establish trusted settlement.
    # --------------------------------------------------------
    gate = StackSettlementGate()

    assert (
        gate.observe(
            obs(
                20,
                17.0,
                confidence=0.80,
                votes=1,
            ),
            phase="PREFLOP",
        )
        is None
    )

    assert (
        gate.observe(
            obs(
                21,
                17.0,
                confidence=0.80,
                votes=1,
            ),
            phase="PREFLOP",
        )
        is None
    )

    # --------------------------------------------------------
    # Contradictory values do not settle.
    # --------------------------------------------------------
    gate = StackSettlementGate()

    assert (
        gate.observe(
            obs(30, 17.0),
            phase="PREFLOP",
        )
        is None
    )

    assert (
        gate.observe(
            obs(31, 7.0),
            phase="PREFLOP",
        )
        is None
    )

    # --------------------------------------------------------
    # Decimal-collapse / huge transition remains blocked
    # without independent commitment evidence.
    # --------------------------------------------------------
    gate = StackSettlementGate()

    huge1 = obs(
        40,
        2.0,
        prior=20.12,
    )
    huge2 = obs(
        41,
        2.0,
        prior=20.12,
    )

    assert (
        gate.observe(
            huge1,
            phase="FLOP",
        )
        is None
    )

    assert (
        gate.observe(
            huge2,
            phase="FLOP",
        )
        is None
    )

    # Same transition may settle when independently corroborated.
    gate = StackSettlementGate()

    assert (
        gate.observe(
            huge1,
            phase="FLOP",
            has_commitment_evidence=True,
        )
        is None
    )

    settled = gate.observe(
        huge2,
        phase="FLOP",
        has_commitment_evidence=True,
    )

    assert settled is not None
    assert settled.delta_bb == 18.12

    print(
        "V0.17 STACK SETTLEMENT GATE: PASS"
    )


if __name__ == "__main__":
    main()
