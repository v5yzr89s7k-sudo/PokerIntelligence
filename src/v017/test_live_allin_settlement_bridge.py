from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


def observation(
    *,
    frame,
    value,
):
    return {
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat":
            "seat_mid_right",
        "frame":
            frame,
        "resolved":
            True,
        "resolved_value":
            value,
        "prior":
            22.94,
        "confidence":
            0.80,
        "votes":
            1,
        "mode":
            "native_green_fast",
    }


def main():
    # --------------------------------------------------------
    # Zero stack WITHOUT bet evidence must remain blocked.
    # --------------------------------------------------------

    gate = StackSettlementGate()

    assert gate.observe(
        observation(
            frame=25,
            value=0.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=False,
        all_in_confirmed=False,
    ) is None

    assert gate.observe(
        observation(
            frame=26,
            value=0.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=False,
        all_in_confirmed=False,
    ) is None

    print(
        "zero without physical commitment: BLOCKED"
    )

    # --------------------------------------------------------
    # Same two-frame zero transition WITH confirmed physical
    # commitment is valid all-in evidence.
    # --------------------------------------------------------

    gate = StackSettlementGate()

    assert gate.observe(
        observation(
            frame=25,
            value=0.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
        all_in_confirmed=True,
    ) is None

    settled = gate.observe(
        observation(
            frame=26,
            value=0.0,
        ),
        phase="PREFLOP",
        has_commitment_evidence=True,
        all_in_confirmed=True,
    )

    assert settled is not None

    assert settled.seat == "seat_mid_right"
    assert abs(settled.prior - 22.94) < 0.001
    assert abs(settled.value - 0.0) < 0.001
    assert abs(settled.delta_bb - 22.94) < 0.001

    print(
        "confirmed settlement =",
        settled,
    )

    print()
    print(
        "V0.17 LIVE ALL-IN SETTLEMENT BRIDGE: PASS"
    )


if __name__ == "__main__":
    main()
