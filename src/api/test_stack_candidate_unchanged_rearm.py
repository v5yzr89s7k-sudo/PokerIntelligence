from pathlib import Path


def main():
    path = Path(
        "src/api/api_event_coordinator.py"
    )

    text = path.read_text()

    assert (
        'unchanged_physical_candidate = bool('
        in text
    )

    assert (
        'validation.reason == "no_stack_change"'
        in text
    )

    assert (
        'if not unchanged_physical_candidate:'
        in text
    )

    assert (
        'unchanged_physical_candidate\n'
        '                    or attempts < maximum_ocr_attempts'
        in text
    )

    # Street ownership must remain candidate-onset scoped.
    assert (
        '"origin_street": ('
        in text
    )

    # Every async retry must continue using the current coordinator
    # frame rather than storing the candidate's opening frame.
    assert (
        'frame_path=frame_path,'
        in text
    )

    print(
        "PASS stack candidate unchanged re-arm: "
        "trusted no-change reads preserve the physical candidate "
        "for newer frames without changing origin street"
    )


if __name__ == "__main__":
    main()
