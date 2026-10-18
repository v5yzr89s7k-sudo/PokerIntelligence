from types import SimpleNamespace

from src.v017.run_live_observer import (
    FrameTransactionState,
    retire_orphan_settlement_candidates,
)


class Observer:
    def __init__(self):
        self.quantitative_retry_pending = {}
        self.quantitative_confirmation_pending = {}
        self.unresolved_quantitative_motion = {
            "villain": {
                "first_frame": 10,
                "last_frame": 17,
                "reason": "stack_motion",
                "commitment_seen": False,
            }
        }

        self.pending_street_boundaries = [
            {
                "observation": {
                    "frame": 30,
                    "type": "FLOP_BOUNDARY_PHYSICAL",
                },
                "action_order": ["villain"],
                "board": None,
                "complete_pending": False,
            }
        ]

    def clear_quantitative_ownership(self, seat):
        seat = str(seat)
        self.unresolved_quantitative_motion.pop(
            seat,
            None,
        )
        self.quantitative_retry_pending.pop(
            seat,
            None,
        )
        self.quantitative_confirmation_pending.pop(
            seat,
            None,
        )


def main():
    observer = Observer()
    state = FrameTransactionState()

    candidate = SimpleNamespace(
        first_frame=17,
    )

    state.settlement_gate.pending["villain"] = candidate
    state.quantitative_first_seen_frame["villain"] = 17
    state.quantitative_first_seen_ns["villain"] = 1

    retired = retire_orphan_settlement_candidates(
        observer,
        state,
        current_frame=31,
    )

    assert retired == ("villain",), retired

    assert "villain" not in state.settlement_gate.pending

    assert (
        "villain"
        not in observer.unresolved_quantitative_motion
    ), (
        "RED: orphan settlement retirement left "
        "unresolved physical-motion ownership alive"
    )

    boundary = observer.pending_street_boundaries[0]

    assert boundary["complete_pending"] is True, boundary

    print(
        "ORPHAN SETTLEMENT RETIREMENT CLEARS "
        "OBSERVER OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
