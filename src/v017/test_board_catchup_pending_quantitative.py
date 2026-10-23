
"""Board catch-up must not overtake unresolved chip commitment."""

from src.v017.test_live_board_catchup import make_observer
from src.v017.run_live_observer import admit_board_catchup


def main():
    observer = make_observer()

    # FLOP is admitted from an already-closed preflop.
    observer.admit_street_boundary(
        {
            "frame": 90,
            "type": "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
        },
        action_order=["hero", "bb"],
        board=["2h", "9c", "Ts"],
    )

    assert observer.hand.street == "FLOP"
    assert observer.hand.next_actor is not None

    # Independent unresolved quantitative ownership.
    observer.quantitative_confirmation_pending["hero"] = {
        "first_frame": 95,
        "street": "FLOP",
        "value": 45.0,
    }

    before = len(observer.hand.actions)

    admit_board_catchup(
        observer,
        frame_id=100,
        board=["2h", "9c", "Ts", "Td", "7s"],
    )

    print("street=", observer.hand.street)
    print("actions_before=", before)
    print("actions_after=", len(observer.hand.actions))

    assert observer.hand.street == "FLOP", (
        "RED: BOARD CATCHUP OVERTOOK QUANTITATIVE OWNERSHIP"
    )

    print("BOARD CATCHUP QUANTITATIVE BARRIER: PASS")


if __name__ == "__main__":
    main()
