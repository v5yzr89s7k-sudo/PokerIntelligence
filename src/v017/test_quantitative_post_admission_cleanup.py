from src.v017.stack_settlement_gate import (
    PendingStackSettlement,
    StackSettlementGate,
)


class FakeObserver:
    def __init__(self):
        self.quantitative_retry_pending = {
            "hero": {
                "attempts": 2,
            },
        }
        self.quantitative_confirmation_pending = {
            "hero": {
                "value": 10.0,
                "first_frame": 10,
                "attempts": 0,
            },
        }

    def clear_quantitative_ownership(
        self,
        seat,
    ):
        self.quantitative_retry_pending.pop(
            seat,
            None,
        )
        self.quantitative_confirmation_pending.pop(
            seat,
            None,
        )


def main():
    # Gate cleanup is seat-local.
    gate = StackSettlementGate()

    gate.pending["hero"] = (
        PendingStackSettlement(
            value=10.0,
            first_frame=10,
        )
    )

    gate.pending["villain"] = (
        PendingStackSettlement(
            value=20.0,
            first_frame=11,
        )
    )

    gate.clear_seat("hero")

    assert "hero" not in gate.pending
    assert "villain" in gate.pending

    # Observer cleanup is also seat-local.
    observer = FakeObserver()

    observer.clear_quantitative_ownership(
        "hero"
    )

    assert (
        "hero"
        not in observer.quantitative_retry_pending
    )
    assert (
        "hero"
        not in observer.quantitative_confirmation_pending
    )

    print(
        "V0.17 POST-ADMISSION QUANTITATIVE CLEANUP: PASS"
    )


if __name__ == "__main__":
    main()
