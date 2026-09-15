from pathlib import Path
import cv2
import json

from src.events.detectors.card_presence import (
    opponent_cards_visible,
)
from src.vision.stack_reader import (
    read_stack_independent_consensus,
)

from src.v017.hand_engine import HandEngine
from src.v017.raw_evidence_bridge import RawEvidenceBridge
from src.v017.test_july22_preflop_vertical_slice import (
    PLAYERS,
    ACTION_ORDER,
)


SESSION = Path(
    "runtime/debug/action_sequence/20260722_152155"
)

GEOM = json.loads(
    Path("config/geometry.json").read_text()
)


def frame(number):
    path = SESSION / f"{number:04d}_full.png"

    img = cv2.imread(str(path))

    if img is None:
        raise RuntimeError(
            f"cannot read {path}"
        )

    if img.shape[1] != 934 or img.shape[0] != 696:
        img = cv2.resize(
            img,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    return img


def cards_visible(number, seat):
    regions = (
        GEOM.get("hole_cards", {})
        .get(seat)
    )

    if not regions:
        raise RuntimeError(
            f"missing hole-card geometry: {seat}"
        )

    return bool(
        opponent_cards_visible(
            frame(number),
            regions,
        )
    )


def stack_value(number, seat):
    img = frame(number)

    region = (
        GEOM.get("stack_regions", {})
        .get(seat)
    )

    if not region:
        raise RuntimeError(
            f"missing stack geometry: {seat}"
        )

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    crop = img[
        y:y + h,
        x:x + w,
    ]

    result = read_stack_independent_consensus(
        crop
    )

    if not isinstance(result, dict):
        raise RuntimeError(
            f"invalid stack result: {result!r}"
        )

    value = result.get("stack_bb")

    if value is None:
        raise RuntimeError(
            f"no stack value seat={seat} frame={number}"
        )

    return float(value)


def require_disappearance(
    bridge,
    seat,
    before_frame,
    after_frame,
):
    before = cards_visible(
        before_frame,
        seat,
    )

    after = cards_visible(
        after_frame,
        seat,
    )

    print(
        seat,
        f"{before_frame:04d}->{after_frame:04d}",
        f"{before}->{after}",
    )

    assert before is True, (
        f"{seat} not visible before disappearance"
    )

    assert after is False, (
        f"{seat} still visible after disappearance"
    )

    bridge.submit_cards_disappeared(
        after_frame,
        seat,
    )


def main():
    hand = HandEngine(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
    )

    bridge = RawEvidenceBridge(hand)

    print()
    print("===== PIXEL CARD DISAPPEARANCES =====")

    # LJ
    require_disappearance(
        bridge,
        "seat_upper_left",
        37,
        38,
    )

    # HJ
    require_disappearance(
        bridge,
        "seat_upper_right",
        39,
        40,
    )

    # CO
    require_disappearance(
        bridge,
        "seat_mid_right",
        39,
        40,
    )

    print()
    print("===== PIXEL STACK TRANSITIONS =====")

    btn_before = stack_value(
        41,
        "seat_lower_right",
    )

    btn_after = stack_value(
        42,
        "seat_lower_right",
    )

    btn_delta = round(
        btn_before - btn_after,
        2,
    )

    print(
        "BTN",
        btn_before,
        "->",
        btn_after,
        "delta=",
        btn_delta,
    )

    assert btn_before == 58.55
    assert btn_after == 56.55
    assert btn_delta == 2.0

    _, btn_action = (
        bridge.submit_stack_commitment(
            42,
            "seat_lower_right",
            btn_delta,
        )
    )

    hero_before = stack_value(
        47,
        "hero",
    )

    hero_after = stack_value(
        48,
        "hero",
    )

    hero_delta = round(
        hero_before - hero_after,
        2,
    )

    print(
        "Hero",
        hero_before,
        "->",
        hero_after,
        "delta=",
        hero_delta,
    )

    assert hero_before == 11.78
    assert hero_after == 10.28
    assert hero_delta == 1.5

    _, hero_action = (
        bridge.submit_stack_commitment(
            48,
            "hero",
            hero_delta,
        )
    )

    print()
    print("===== OBJECTIVE EVIDENCE =====")

    for item in bridge.observations():
        print(item)

    print()
    print("===== SEMANTIC RESULT =====")

    voluntary = [
        item
        for item in hand.semantic_actions()
        if item["action"] not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    for item in voluntary:
        print(item)

    observed = [
        (
            item["seat"],
            item["action"],
            item["amount_bb"],
            item["raise_to_bb"],
        )
        for item in voluntary
    ]

    expected = [
        (
            "seat_upper_left",
            "FOLD",
            None,
            None,
        ),
        (
            "seat_upper_right",
            "FOLD",
            None,
            None,
        ),
        (
            "seat_mid_right",
            "FOLD",
            None,
            None,
        ),
        (
            "seat_lower_right",
            "RAISE",
            None,
            2.0,
        ),
        (
            "hero",
            "CALL",
            1.5,
            None,
        ),
    ]

    assert observed == expected

    assert btn_action == "RAISE"
    assert hero_action == "CALL"
    assert hand.current_price_bb == 2.0
    assert hand.next_actor == "seat_lower_left"

    print()
    print(
        "V0.17 JULY22 FULL PIXEL PREFLOP: PASS"
    )


if __name__ == "__main__":
    main()
