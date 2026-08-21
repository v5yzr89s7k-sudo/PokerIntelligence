from types import SimpleNamespace

from src.api import api_event_coordinator as c


def quiet():
    return SimpleNamespace(
        hero_changed=False,
        board_changed=False,
        pot_changed=False,
        dealer_changed=False,
        action_buttons_changed=False,
        hero_cards_appeared=False,
        hero_cards_cleared=False,
        stack_changed_seats=[],
        bet_region_appeared=[],
        bet_region_cleared=[],
        opponent_hole_card_changed_seats=[],
    )


def main():
    changes = quiet()

    assert (
        c.has_semantic_local_change(changes)
        is False
    )

    changes.opponent_hole_card_changed_seats = [
        "seat_lower_right"
    ]

    assert (
        c.has_semantic_local_change(changes)
        is True
    )

    assert (
        c.change_gate_has_pending_work({
            "pending_stack_reads": {}
        })
        is False
    )

    assert (
        c.change_gate_has_pending_work({
            "pending_stack_reads": {
                "hero": {
                    "origin_street": "FLOP"
                }
            }
        })
        is True
    )

    print(
        "PASS change-gate contract: "
        "quiet samples discardable; opponent-card "
        "transition retained; pending stack settlement protected"
    )


if __name__ == "__main__":
    main()
