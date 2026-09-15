from pathlib import Path
import cv2
import json

from src.vision.stack_reader import (
    read_stack_independent_consensus,
)

from src.v017.hand_engine import HandEngine
from src.v017.raw_evidence_bridge import (
    RawEvidenceBridge,
)
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


def read_stack(frame_number, seat):
    path = (
        SESSION
        / f"{frame_number:04d}_full.png"
    )

    img = cv2.imread(str(path))

    if img is None:
        raise RuntimeError(
            f"cannot read {path}"
        )

    if (
        img.shape[1] != 934
        or img.shape[0] != 696
    ):
        img = cv2.resize(
            img,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    region = (
        GEOM.get("stack_regions", {})
        .get(seat)
    )

    if not region:
        raise RuntimeError(
            f"missing stack region: {seat}"
        )

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    crop = img[
        y:y + h,
        x:x + w,
    ]

    result = (
        read_stack_independent_consensus(
            crop
        )
    )

    if not isinstance(result, dict):
        raise RuntimeError(
            f"invalid stack result: {result!r}"
        )

    value = result.get("stack_bb")

    if value is None:
        raise RuntimeError(
            f"no stack value: {seat} frame={frame_number}"
        )

    return float(value), result


def main():
    hand = HandEngine(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
    )

    bridge = RawEvidenceBridge(hand)

    # Card-disappearance events remain the already-proven
    # objective observations for this A2 sizing boundary.
    bridge.submit_cards_disappeared(
        38,
        "seat_upper_left",
    )

    bridge.submit_cards_disappeared(
        40,
        "seat_upper_right",
    )

    bridge.submit_cards_disappeared(
        40,
        "seat_mid_right",
    )

    # ---------------------------------------------------------
    # BTN — values come directly from July 22 pixels.
    # ---------------------------------------------------------

    btn_before, btn_before_raw = read_stack(
        41,
        "seat_lower_right",
    )

    btn_after, btn_after_raw = read_stack(
        42,
        "seat_lower_right",
    )

    btn_delta = round(
        btn_before - btn_after,
        2,
    )

    print()
    print("===== BTN PIXEL MEASUREMENT =====")
    print("before =", btn_before)
    print("after  =", btn_after)
    print("delta  =", btn_delta)
    print(
        "before confidence =",
        btn_before_raw.get("confidence"),
    )
    print(
        "after confidence  =",
        btn_after_raw.get("confidence"),
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

    # ---------------------------------------------------------
    # HERO — values come directly from July 22 pixels.
    # ---------------------------------------------------------

    hero_before, hero_before_raw = read_stack(
        47,
        "hero",
    )

    hero_after, hero_after_raw = read_stack(
        48,
        "hero",
    )

    hero_delta = round(
        hero_before - hero_after,
        2,
    )

    print()
    print("===== HERO PIXEL MEASUREMENT =====")
    print("before =", hero_before)
    print("after  =", hero_after)
    print("delta  =", hero_delta)
    print(
        "before confidence =",
        hero_before_raw.get("confidence"),
    )
    print(
        "after confidence  =",
        hero_after_raw.get("confidence"),
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
    print("===== RAW EVIDENCE =====")

    for item in bridge.observations():
        print(item)

    print()
    print("===== HAND ENGINE =====")

    for item in hand.semantic_actions():
        print(item)

    assert btn_action == "RAISE"
    assert hero_action == "CALL"

    voluntary = [
        item
        for item in hand.semantic_actions()
        if item["action"]
        not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

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

    assert hand.current_price_bb == 2.0
    assert (
        hand.players[
            "seat_lower_right"
        ].street_commitment_bb
        == 2.0
    )
    assert (
        hand.players[
            "hero"
        ].street_commitment_bb
        == 2.0
    )
    assert hand.next_actor == "seat_lower_left"

    print()
    print(
        "V0.17 JULY22 PIXEL PREFLOP: PASS"
    )


if __name__ == "__main__":
    main()
