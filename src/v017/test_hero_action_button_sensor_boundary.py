from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "src/v017/frame_hand_observer.py"
).read_text()


def main():
    assert (
        "action_buttons_visible"
        in SOURCE
    )

    assert (
        "previous_action_buttons_visible"
        in SOURCE
    )

    assert (
        "HERO_ACTION_BUTTONS_APPEARED"
        in SOURCE
    )

    assert (
        "HERO_ACTION_BUTTONS_DISAPPEARED"
        in SOURCE
    )

    # Physical sensor only. It must not directly assign semantics.
    appeared = SOURCE.index(
        '"HERO_ACTION_BUTTONS_APPEARED"'
    )

    disappeared = SOURCE.index(
        '"HERO_ACTION_BUTTONS_DISAPPEARED"'
    )

    local = SOURCE[
        min(appeared, disappeared) - 1000:
        max(appeared, disappeared) + 1000
    ]

    assert (
        "observe_fold("
        not in local
    )

    assert (
        "observe_no_commitment("
        not in local
    )

    assert (
        "observe_stack_commitment("
        not in local
    )

    print(
        "V0.17 HERO ACTION-BUTTON SENSOR BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
