from pathlib import Path
from unittest.mock import patch

from src.v017 import run_live_observer as live


def main():
    directory = live.SCK_MATERIALIZED_FRAME_DIR

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    fake_a = directory / "sck_frame_00000123.png"
    fake_b = directory / "sck_frame_00000999.png"

    fake_a.write_bytes(b"old-hand-a")
    fake_b.write_bytes(b"old-hand-b")

    live._SCK_CAPTURE_SEQUENCE = 999

    live.reset_hand_frame_storage()

    assert not fake_a.exists()
    assert not fake_b.exists()

    assert list(
        directory.glob("sck_frame_*.png")
    ) == []

    assert live._SCK_CAPTURE_SEQUENCE == 0

    source = Path(
        "src/v017/run_live_observer.py"
    ).read_text()

    start = source.index(
        "def bootstrap_observer("
    )
    end = source.index(
        "\ndef ",
        start + 5,
    )

    bootstrap = source[start:end]

    assert (
        "reset_hand_frame_storage()"
        in bootstrap
    )

    print(
        "HAND-LOCAL FRAME STORAGE CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
