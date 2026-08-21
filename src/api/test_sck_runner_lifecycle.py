from pathlib import Path
import ast


def main():
    text = Path(
        "src/api/run_live_observer.py"
    ).read_text()

    ast.parse(text)

    required = [
        "def start_native(",
        "def build_sck_sampler(",
        "def start_sck_sampler(",
        '"sck_sampler"',
        '"POKER_SCK_CAPTURE"',
        '"POKER_REPLAY_SESSION"',
        'terminate_process("sck_sampler")',
        "swiftc",
        "-parse-as-library",
    ]

    missing = [
        item
        for item in required
        if item not in text
    ]

    assert not missing, (
        "missing SCK runner lifecycle elements: "
        + ", ".join(missing)
    )

    # Existing Python worker launcher must remain.
    assert (
        "[sys.executable, *args]"
        in text
    )

    # Coordinator still launched through normal Python path.
    assert (
        '"coordinator",'
        in text
        and '"src/api/api_event_coordinator.py"'
        in text
    )

    print(
        "PASS SCK runner lifecycle: "
        "live owns native sampler startup/shutdown; "
        "replay bypass remains explicit"
    )


if __name__ == "__main__":
    main()
