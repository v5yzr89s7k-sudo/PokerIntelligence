import cv2
import json
from pathlib import Path

from src.vision.stack_reader import read_stack


ROOT = Path(__file__).resolve().parents[2]
SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260812_104222"
)

GEOM = json.loads(
    (ROOT / "config/geometry.json").read_text()
)


def read_frame(index, seat):
    path = SESSION / f"{index:04d}_full.png"

    if not path.exists():
        raise AssertionError(
            f"Replay 0001 frame missing: {path}"
        )

    image = cv2.imread(str(path))
    assert image is not None

    image = cv2.resize(
        image,
        (934, 696),
    )

    r = GEOM["stack_regions"][seat]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    return read_stack(
        image[y:y+h, x:x+w]
    )


def values(reading):
    return {
        item.get("stack_bb")
        for item in reading.get("raw") or []
        if item.get("stack_bb") is not None
    }


def main():
    # Stable BB baseline is unambiguous.
    baseline = read_frame(
        49,
        "seat_mid_left",
    )

    assert baseline["stack_bb"] == 65.6, baseline
    assert baseline["votes"] >= 2, baseline

    # Post-3-bet PSM7 and PSM13 disagree. The reader must preserve both
    # candidates and refuse to declare either authoritative.
    after_three_bet = read_frame(
        51,
        "seat_mid_left",
    )

    assert 96.6 in values(after_three_bet), after_three_bet
    assert 56.6 in values(after_three_bet), after_three_bet
    assert after_three_bet["votes"] == 1, after_three_bet
    assert (
        after_three_bet["mode"]
        == "segmentation_disagreement"
    ), after_three_bet

    # Hero provides the complementary safety regression. PSM13 must not
    # blindly override the agreeing PSM7 result with 80.84.
    hero_noisy = read_frame(
        69,
        "hero",
    )

    assert 90.84 in values(hero_noisy), hero_noisy
    assert 80.84 in values(hero_noisy), hero_noisy
    assert hero_noisy["votes"] == 1, hero_noisy
    assert (
        hero_noisy["mode"]
        == "segmentation_disagreement"
    ), hero_noisy

    # Stable Hero response eventually resolves normally to the real 50.84.
    hero_settled = read_frame(
        66,
        "hero",
    )

    assert hero_settled["stack_bb"] == 50.84, hero_settled
    assert hero_settled["votes"] >= 2, hero_settled

    print(
        "PASS Replay 0001 stack OCR evidence: "
        "PSM13 disagreement preserved for continuity; "
        "stable Hero stack resolves to 50.84"
    )


if __name__ == "__main__":
    main()
