from pathlib import Path
import ast


def main():
    text = Path(
        "src/api/api_event_coordinator.py"
    ).read_text()

    ast.parse(text)

    main_text = text[
        text.index("def main():"):
    ]

    assert (
        '"change_gate": "settlement_tick"'
        in main_text
    )

    assert (
        '"change_gate": "discarded_quiet"'
        in main_text
    )

    settlement = main_text.index(
        '"change_gate": "settlement_tick"'
    )

    startup = main_text.index(
        "retry_one_startup_stack("
    )

    winner = main_text.index(
        "detect_winner("
    )

    observer = main_text.index(
        "observer.ingest_changes("
    )

    # Minimal settlement branch must terminate before the ordinary
    # expensive semantic stages.
    assert settlement < startup
    assert settlement < winner
    assert settlement < observer

    print(
        "PASS change gate V2 structure: "
        "quiet settlement terminates before startup OCR, "
        "winner detection and observer pipeline"
    )


if __name__ == "__main__":
    main()
