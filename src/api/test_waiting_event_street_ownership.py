from src.api.api_event_coordinator import event_street_for_frame


def main():
    waiting = {"phase": "WAITING"}

    for board_count in (0, 1, 2, 3, 4, 5):
        observed = event_street_for_frame(
            waiting,
            board_count,
        )

        print(
            "WAITING",
            "board_count=",
            board_count,
            "event_street=",
            observed,
        )

        assert observed == "WAITING", (
            "WAITING pixels acquired provisional "
            f"street ownership: board_count={board_count} "
            f"observed={observed}"
        )

    preflop = {"phase": "PREFLOP"}

    assert (
        event_street_for_frame(preflop, 3)
        == "FLOP"
    )
    assert (
        event_street_for_frame(
            {"phase": "FLOP"},
            4,
        )
        == "TURN"
    )
    assert (
        event_street_for_frame(
            {"phase": "TURN"},
            5,
        )
        == "RIVER"
    )

    print(
        "PASS: WAITING owns no provisional "
        "postflop street"
    )


if __name__ == "__main__":
    main()
