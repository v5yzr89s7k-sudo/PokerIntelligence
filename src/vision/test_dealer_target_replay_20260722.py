from pathlib import Path

from src.vision.dealer_detector import detect_dealer_button


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/debug/action_sequence/20260722_152155"
    / "0012_full.png"
)


def main():
    if not FRAME.exists():
        raise SystemExit(
            f"missing recorded regression frame: {FRAME}"
        )

    result = detect_dealer_button(FRAME)

    detected = result.get("dealer_button_seat")
    best = result.get("best") or {}

    expected = "seat_lower_right"

    assert detected == expected, (
        "July 22 target hand dealer ownership regression: "
        f"expected={expected} "
        f"detected={detected} "
        f"zone={best.get('zone_index')} "
        f"confidence={best.get('confidence')} "
        f"xy=({best.get('match_x')},{best.get('match_y')})"
    )

    assert best.get("match_x") == 648
    assert best.get("match_y") == 413

    print(
        "PASS target replay dealer ownership: "
        "physical D at (648,413) belongs to "
        "seat_lower_right"
    )


if __name__ == "__main__":
    main()
