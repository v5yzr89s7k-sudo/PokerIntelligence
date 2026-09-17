from unittest.mock import patch

from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)
from src.api.stack_transition_validator import (
    ACCEPT,
    StackTransitionValidation,
)


def native_obs(frame):
    return {
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "frame": frame,
        "seat": "hero",
        "prior": 30.0,
        "resolved": True,
        "resolved_value": 28.0,
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
    }


def main():
    gate = StackSettlementGate()

    calls = []

    def fake_validator(
        previous,
        current,
        *,
        confidence,
        votes,
        phase,
        has_commitment_evidence=False,
        all_in_confirmed=False,
    ):
        calls.append({
            "previous": previous,
            "current": current,
            "confidence": confidence,
            "votes": votes,
            "phase": phase,
            "has_commitment_evidence":
                has_commitment_evidence,
            "all_in_confirmed":
                all_in_confirmed,
        })

        return StackTransitionValidation(
            decision=ACCEPT,
            reason="test_accept",
            previous_stack_bb=float(previous),
            current_stack_bb=float(current),
            delta_bb=round(
                float(previous)
                - float(current),
                2,
            ),
            large_commitment=False,
        )

    with patch(
        "src.v017.stack_settlement_gate."
        "validate_stack_transition",
        side_effect=fake_validator,
    ):
        first = gate.observe(
            native_obs(100),
            phase="PREFLOP",
            has_commitment_evidence=True,
        )

        assert first is None

        # Validator must not run after only one native frame.
        assert calls == []

        second = gate.observe(
            native_obs(101),
            phase="PREFLOP",
            has_commitment_evidence=True,
        )

        assert second is not None

    assert len(calls) == 1

    call = calls[0]

    assert call["confidence"] >= 0.95
    assert call["votes"] >= 2

    # The bridge promotes only validator-facing aggregate evidence.
    original = native_obs(101)

    assert original["confidence"] == 0.80
    assert original["votes"] == 1

    print(
        "validator evidence =",
        call,
    )

    print(
        "V0.17 NATIVE SETTLEMENT VALIDATOR BRIDGE: PASS"
    )


if __name__ == "__main__":
    main()
