from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


def observation(
    *,
    frame,
    value,
    prior=30.0,
    mode="native_green_fast",
    confidence=0.80,
    votes=1,
):
    return {
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat":
            "hero",
        "frame":
            frame,
        "resolved":
            True,
        "resolved_value":
            value,
        "prior":
            prior,
        "confidence":
            confidence,
        "votes":
            votes,
        "mode":
            mode,
    }


def main():
    # --------------------------------------------------------
    # Native fast: one frame is NEVER enough.
    # --------------------------------------------------------
    gate = StackSettlementGate()

    first = gate.observe(
        observation(
            frame=10,
            value=28.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
    )

    assert first is None

    assert "hero" in gate.pending
    assert gate.pending["hero"].first_frame == 10

    # Same source frame cannot confirm itself.
    same_frame = gate.observe(
        observation(
            frame=10,
            value=28.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
    )

    assert same_frame is None
    assert "hero" in gate.pending

    # Independent later frame with same value settles.
    second = gate.observe(
        observation(
            frame=11,
            value=28.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
    )

    assert second is not None
    assert second.seat == "hero"
    assert abs(second.prior - 30.0) < 0.001
    assert abs(second.value - 28.0) < 0.001
    assert abs(second.delta_bb - 2.0) < 0.001
    assert "hero" not in gate.pending

    # Individual native metadata remains one-read metadata.
    # Settlement authority came from agreement across frame 10
    # and frame 11, not by mutating either observation.
    source = observation(
        frame=11,
        value=28.0,
    )
    assert source["confidence"] == 0.80
    assert source["votes"] == 1
    assert source["mode"] == "native_green_fast"

    # --------------------------------------------------------
    # Contradiction starts a fresh candidate epoch.
    # --------------------------------------------------------
    gate = StackSettlementGate()

    assert gate.observe(
        observation(
            frame=20,
            value=29.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
    ) is None

    assert gate.observe(
        observation(
            frame=21,
            value=28.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
    ) is None

    assert gate.pending["hero"].first_frame == 21
    assert abs(
        gate.pending["hero"].value
        - 28.0
    ) < 0.001

    settled = gate.observe(
        observation(
            frame=22,
            value=28.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
    )

    assert settled is not None

    # --------------------------------------------------------
    # Weak legacy green-only remains rejected.
    # --------------------------------------------------------
    gate = StackSettlementGate()

    weak = observation(
        frame=30,
        value=28.0,
        mode="green_only",
        confidence=0.80,
        votes=1,
    )

    assert gate.observe(
        weak,
        phase="PREFLOP",
        has_commitment_evidence=True,
    ) is None

    assert "hero" not in gate.pending

    # --------------------------------------------------------
    # Existing consensus authority still works.
    # --------------------------------------------------------
    gate = StackSettlementGate()

    consensus1 = observation(
        frame=40,
        value=28.0,
        mode="agreement_verified",
        confidence=0.98,
        votes=2,
    )

    consensus2 = observation(
        frame=41,
        value=28.0,
        mode="agreement_verified",
        confidence=0.98,
        votes=2,
    )

    assert gate.observe(
        consensus1,
        phase="PREFLOP",
        has_commitment_evidence=True,
    ) is None

    assert gate.observe(
        consensus2,
        phase="PREFLOP",
        has_commitment_evidence=True,
    ) is not None

    print(
        "V0.17 NATIVE TWO-FRAME SETTLEMENT: PASS"
    )


if __name__ == "__main__":
    main()
