from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "src/v017/frame_hand_observer.py"
).read_text()


def main():
    required = (
        "self.quantitative_confirmation_pending = {}",
        "self.quantitative_confirmation_max_attempts",
        "confirmation_owned = bool(",
        "[QUANTITATIVE_CONFIRMATION_ARMED]",
        "[QUANTITATIVE_CONFIRMATION_OBSERVED]",
        "[QUANTITATIVE_CONFIRMATION_EXHAUSTED]",
    )

    for token in required:
        assert token in SOURCE, token

    # Confirmation remains frame-driven.
    forbidden = (
        "time.sleep(",
        "capture_window_crop(",
        "capture_image(",
    )

    for token in forbidden:
        assert token not in SOURCE, token

    print(
        "V0.17 QUANTITATIVE CONFIRMATION OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
