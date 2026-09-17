from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "src/v017/frame_hand_observer.py"
).read_text()


def main():
    required = (
        "self.quantitative_retry_pending = {}",
        "self.quantitative_retry_max_attempts",
        "retry_owned = bool(",
        "seat in self.confirmed_bet_regions",
        "[QUANTITATIVE_RETRY_ARMED]",
        "[QUANTITATIVE_RETRY_RESOLVED]",
        "[QUANTITATIVE_RETRY_EXHAUSTED]",
    )

    for token in required:
        assert token in SOURCE, token

    # Retry must remain frame-driven. No sleeps/captures/API work
    # may be introduced into FrameHandObserver.
    forbidden = (
        "time.sleep(",
        "capture_window_crop(",
        "capture_image(",
        "read_hero_cards(",
        "read_board(",
    )

    for token in forbidden:
        assert token not in SOURCE, token

    print(
        "V0.17 QUANTITATIVE RETRY SAFETY: PASS"
    )


if __name__ == "__main__":
    main()
