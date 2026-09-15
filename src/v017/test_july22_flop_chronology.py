from pathlib import Path
import cv2
import json

from src.vision.stack_reader import (
    read_stack,
    read_stack_independent_consensus,
)

from src.v017.hand_engine import HandEngine
from src.v017.stack_continuity import (
    select_continuity_candidate,
)
from src.v017.test_july22_preflop_vertical_slice import (
    PLAYERS,
    ACTION_ORDER,
)


ROOT = Path(
    "runtime/debug/action_sequence/20260722_152155"
)

GEOM = json.loads(
    Path("config/geometry.json").read_text()
)


def crop(number, seat):
    img = cv2.imread(
        str(ROOT / f"{number:04d}_full.png")
    )

    if img is None:
        raise RuntimeError(number)

    if img.shape[:2] != (696, 934):
        img = cv2.resize(
            img,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    r = GEOM["stack_regions"][seat]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    return img[y:y+h, x:x+w]


def stack_candidates(number, seat):
    c = crop(number, seat)

    return (
        read_stack(c),
        read_stack_independent_consensus(c),
    )


def build_preflop():
    hand = HandEngine(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
    )

    hand.observe_cards_disappeared(
        "seat_upper_left"
    )
    hand.observe_cards_disappeared(
        "seat_upper_right"
    )
    hand.observe_cards_disappeared(
        "seat_mid_right"
    )

    hand.observe_stack_commitment(
        "seat_lower_right",
        2.0,
    )

    hand.observe_stack_commitment(
        "hero",
        1.5,
    )

    # BB closes preflop by calling the remaining 1 BB.
    hand.observe_stack_commitment(
        "seat_lower_left",
        1.0,
    )

    assert hand.next_actor is None

    return hand


def main():
    hand = build_preflop()

    hand.start_street(
        "FLOP",
        [
            "hero",
            "seat_lower_left",
            "seat_lower_right",
        ],
    )

    assert hand.next_actor == "hero"
    assert hand.current_price_bb == 0.0

    print("===== HERO PRE-BB STACK CONTINUITY =====")

    previous = 10.28

    # Sample widely across the interval before BB's confirmed
    # frame-0090 stack transition.
    for number in (
        52,
        60,
        70,
        80,
        85,
        88,
        89,
    ):
        normal, independent = stack_candidates(
            number,
            "hero",
        )

        selected = select_continuity_candidate(
            previous,
            normal,
            independent,
            max_drop_bb=previous,
        )

        print(
            number,
            "normal=",
            normal.get("stack_bb"),
            "independent=",
            independent.get("stack_bb"),
            "selected=",
            selected,
        )

        # No downward candidate is allowed before BB acts.
        # Equal 10.28 is not a transition and therefore selection
        # may legitimately return None.
        for result in (
            normal,
            independent,
        ):
            value = result.get("stack_bb")

            if value is not None and value <= previous:
                assert abs(
                    float(value) - previous
                ) < 0.001, (
                    f"Hero stack moved before BB at frame {number}: "
                    f"{value}"
                )

    print()
    print("Hero remained 10.28 BB before BB commitment")

    # A later actor's independently proven physical commitment
    # establishes that Hero's preceding turn completed.
    #
    # Hero committed no chips and faced price zero.
    # HandEngine therefore owns the semantic classification.
    hero_action = hand.observe_no_commitment(
        "hero"
    )

    assert hero_action == "CHECK"
    assert hand.next_actor == "seat_lower_left"

    print()
    print("===== BB QUANTITATIVE ACTION =====")

    # Trusted post-preflop BB stack:
    # 48.57 starting - 1.00 blind = 47.57.
    #
    # Pixel evidence settles at 44.20 beginning frame 0090.
    bb_delta = round(
        47.57 - 44.20,
        2,
    )

    assert bb_delta == 3.37

    bb_action = hand.observe_stack_commitment(
        "seat_lower_left",
        bb_delta,
    )

    print(
        "BB action =",
        bb_action,
    )

    print(
        "price =",
        hand.current_price_bb,
    )

    print(
        "next actor =",
        hand.next_actor,
    )

    assert bb_action in {
        "BET",
        "RAISE",
    }

    assert hand.current_price_bb == 3.37
    assert hand.next_actor == "seat_lower_right"

    # BTN physically disappears at frame 0097.
    btn_action = hand.observe_cards_disappeared(
        "seat_lower_right"
    )

    assert btn_action == "FOLD"

    # After BTN folds, Hero must respond to BB's 3.37.
    assert hand.next_actor == "hero"

    print()
    print("===== HERO RESPONSE =====")

    hero_delta = round(
        10.28 - 6.90,
        2,
    )

    assert hero_delta == 3.38

    # Display/OCR precision differs by 0.01 BB from the visible
    # wager. Normalize the physical stack decrease to the live
    # betting price only at the semantic boundary.
    assert abs(
        hero_delta - hand.current_price_bb
    ) <= 0.02

    hero_response = hand.observe_stack_commitment(
        "hero",
        hand.current_price_bb,
    )

    assert hero_response == "CALL"

    print(
        "Hero physical delta =",
        hero_delta,
    )
    print(
        "Hero semantic commitment =",
        hand.current_price_bb,
    )
    print(
        "Hero action =",
        hero_response,
    )

    assert hand.next_actor is None

    print()
    print("===== FLOP ACTIONS =====")

    flop = [
        action
        for action in hand.semantic_actions()
        if action["street"] == "FLOP"
    ]

    for action in flop:
        print(action)

    observed = [
        (
            action["seat"],
            action["action"],
            action["amount_bb"],
            action["raise_to_bb"],
        )
        for action in flop
    ]

    expected = [
        (
            "hero",
            "CHECK",
            None,
            None,
        ),
        (
            "seat_lower_left",
            "BET",
            3.37,
            None,
        ),
        (
            "seat_lower_right",
            "FOLD",
            None,
            None,
        ),
        (
            "hero",
            "CALL",
            3.37,
            None,
        ),
    ]

    assert observed == expected, observed

    print()
    print(
        "V0.17 JULY22 FLOP CHRONOLOGY: PASS"
    )


if __name__ == "__main__":
    main()
