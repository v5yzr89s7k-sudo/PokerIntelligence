from src.v017.run_live_observer import (
    FrameTransactionState,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)


def main():
    first = FrameTransactionState()
    second = FrameTransactionState()

    assert isinstance(
        first.settlement_gate,
        StackSettlementGate,
    )
    assert (
        first.settlement_gate
        is not second.settlement_gate
    )
    assert first.hero_buttons_active is False
    assert (
        first.hero_completion_pending_frame
        is None
    )

    print("PER-HAND SETTLEMENT OWNERSHIP: PASS")
    print("HERO LIFECYCLE INITIAL STATE: PASS")
    print("V0.17 FRAME TRANSACTION STATE: PASS")


if __name__ == "__main__":
    main()
