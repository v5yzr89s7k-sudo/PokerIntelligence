from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "src/v017/frame_hand_observer.py"
).read_text()


def main():
    required = (
        "reason=seat_not_trusted",
        "reason=unresolved",
        "reason=value_none",
        "reason=no_positive_delta",
        "reason=seat_not_pending",
        "reason=blocked_predecessors",
    )

    for token in required:
        assert token in SOURCE, token

    print(
        "V0.17 QUANTITATIVE REJECTION DIAGNOSTICS: PASS"
    )


if __name__ == "__main__":
    main()
