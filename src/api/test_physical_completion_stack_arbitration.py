from src.api.api_event_state_machine import (
    physical_completion_stack_blocked,
)


def main():
    base = {
        "unresolved_stack_candidates": {},
    }

    # No candidate: never blocked.
    assert not physical_completion_stack_blocked(
        base,
        "FLOP",
        "btn",
    )

    # Motion alone is not commitment evidence.
    motion = {
        "unresolved_stack_candidates": {
            "FLOP:btn": {
                "seat": "btn",
                "street": "FLOP",
                "sources": [
                    "stack_motion",
                ],
            }
        }
    }

    assert not physical_completion_stack_blocked(
        motion,
        "FLOP",
        "btn",
    )

    # Independent chip-region evidence must still protect
    # a potentially quantitative action.
    bet = {
        "unresolved_stack_candidates": {
            "FLOP:btn": {
                "seat": "btn",
                "street": "FLOP",
                "sources": [
                    "stack_motion",
                    "bet_region_appeared",
                ],
            }
        }
    }

    assert physical_completion_stack_blocked(
        bet,
        "FLOP",
        "btn",
    )

    occupied = {
        "unresolved_stack_candidates": {
            "FLOP:btn": {
                "seat": "btn",
                "street": "FLOP",
                "sources": [
                    "bet_region_occupied",
                ],
            }
        }
    }

    assert physical_completion_stack_blocked(
        occupied,
        "FLOP",
        "btn",
    )

    print(
        "PASS physical completion stack arbitration: "
        "stack-motion-only candidates cannot veto calibrated "
        "card disappearance; commitment evidence still blocks"
    )


if __name__ == "__main__":
    main()
