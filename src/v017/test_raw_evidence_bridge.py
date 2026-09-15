from src.v017.hand_engine import HandEngine
from src.v017.raw_evidence_bridge import (
    RawEvidenceBridge,
)
from src.v017.test_july22_preflop_vertical_slice import (
    PLAYERS,
    ACTION_ORDER,
)


def main():
    hand = HandEngine(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
    )

    bridge = RawEvidenceBridge(hand)

    # July 22 objective observation chronology.
    #
    # Frames are evidence anchors only.
    # Poker semantics are NOT supplied here.

    bridge.submit_cards_disappeared(
        1,
        "seat_upper_left",
    )

    bridge.submit_cards_disappeared(
        1,
        "seat_upper_right",
    )

    bridge.submit_cards_disappeared(
        1,
        "seat_mid_right",
    )

    btn_evidence, btn_action = (
        bridge.submit_stack_commitment(
            43,
            "seat_lower_right",
            2.0,
        )
    )

    hero_evidence, hero_action = (
        bridge.submit_stack_commitment(
            52,
            "hero",
            1.5,
        )
    )

    print()
    print("===== RAW EVIDENCE =====")

    for item in bridge.observations():
        print(item)

    print()
    print("===== HAND ENGINE SEMANTICS =====")

    for item in hand.semantic_actions():
        print(item)

    observations = bridge.observations()

    assert [
        item["evidence_type"]
        for item in observations
    ] == [
        "CARDS_DISAPPEARED",
        "CARDS_DISAPPEARED",
        "CARDS_DISAPPEARED",
        "STACK_COMMITMENT",
        "STACK_COMMITMENT",
    ]

    # Critical ownership assertion:
    #
    # Raw evidence vocabulary contains no poker actions.
    forbidden = {
        "FOLD",
        "CALL",
        "BET",
        "RAISE",
        "CHECK",
    }

    for item in observations:
        assert item["evidence_type"] not in forbidden

    assert btn_evidence.frame == 43
    assert btn_evidence.seat == "seat_lower_right"
    assert btn_evidence.delta_bb == 2.0

    assert hero_evidence.frame == 52
    assert hero_evidence.seat == "hero"
    assert hero_evidence.delta_bb == 1.5

    # These semantics must originate from HandEngine.
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

    print()
    print(
        "V0.17 RAW EVIDENCE BRIDGE: PASS"
    )


if __name__ == "__main__":
    main()
