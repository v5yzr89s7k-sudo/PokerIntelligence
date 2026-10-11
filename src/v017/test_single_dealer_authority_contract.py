from pathlib import Path


def main():
    s = Path(
        "src/v017/run_live_observer.py"
    ).read_text()

    start = s.index("def build_observer_from_frame(")
    end = s.index("\ndef bootstrap_observer(", start)
    build = s[start:end]

    assert "confirmed_dealer_seat=None" in build

    assert '''dealer_seat = str(
        confirmed_dealer_seat
        or ""
    )''' in build

    assert (
        'snapshot.get("dealer_button_seat")'
        in build
    )

    assert "[SNAPSHOT_DEALER_IGNORED]" in build

    # Snapshot dealer may be compared diagnostically,
    # but it cannot become position authority.
    position_call = build.index(
        "positions = assign_positions("
    )

    before_position = build[:position_call]

    assert "dealer_seat = str(" in before_position
    assert "confirmed_dealer_seat" in before_position

    bootstrap_start = s.index(
        "def bootstrap_observer("
    )
    bootstrap_end = s.index(
        "\ndef ",
        bootstrap_start + 5,
    )
    bootstrap = s[
        bootstrap_start:bootstrap_end
    ]

    assert "confirmed_dealer_seat" in bootstrap
    assert (
        "confirmed_dealer_seat="
        in bootstrap
    )

    print(
        "SINGLE PHYSICAL DEALER AUTHORITY CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
