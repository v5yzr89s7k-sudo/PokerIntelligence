from pathlib import Path
import ast


def main():
    text = Path(
        "src/api/api_event_coordinator.py"
    ).read_text()

    ast.parse(text)

    assert (
        "from src.capture.sck_frame_source "
        "import SCKFrameSource"
        in text
    )

    assert "def capture_sck_live():" in text

    assert (
        '"POKER_SCK_CAPTURE"'
        in text
    )

    assert (
        "img, frame = capture_sck_live()"
        in text
    )

    # Replay remains the original durable-frame source.
    assert (
        "return replay.capture()"
        in text
    )

    # Existing downstream worker path contract remains intact.
    assert (
        '"frame": str(frame)'
        in text
    )

    print(
        "PASS SCK Phase A structure: "
        "live can consume canonical in-memory frames; "
        "replay and worker frame-path contracts remain intact"
    )


if __name__ == "__main__":
    main()
