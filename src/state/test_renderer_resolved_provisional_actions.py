"""
Resolved ActionTimeline semantics that are still chronology-pending must be
renderable through provisional_actions without becoming CanonicalHand actions.
"""

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_renderer import render_canonical_hand


def main():
    hand = CanonicalHand().start_hand(
        hand_id="resolved-provisional-render",
        players=[
            {
                "seat": "btn",
                "name": "Villain",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 20.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "bb",
                "name": "BB",
                "stack_bb": 40.0,
                "is_active": True,
            },
        ],
        hero_cards=["Ah", "Qd"],
        hero_position="SB",
        positions={
            "btn": "BTN",
            "hero": "SB",
            "bb": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"

    hand.current_street = "PREFLOP"

    hand.add_action(
        seat="hero",
        action="POST_SMALL_BLIND",
        amount_bb=0.5,
        source="test",
    )

    hand.add_action(
        seat="bb",
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        source="test",
    )

    provisional = [
        {
            "street": "PREFLOP",
            "seat": "btn",
            "action": "RAISE",
            "raise_to_bb": 2.0,
            "amount_bb": None,
            "ts": 10.0,
        },
        {
            "street": "PREFLOP",
            "seat": "hero",
            "action": "CALL",
            "amount_bb": 1.5,
            "raise_to_bb": None,
            "ts": 11.0,
        },
    ]

    rendered = render_canonical_hand(
        hand,
        provisional_actions=provisional,
    )

    print(rendered)

    assert "BTN (Villain) raises to 2 BB" in rendered, (
        "resolved provisional RAISE was not rendered with sizing"
    )

    assert "SB (Hero) calls 1.5 BB" in rendered, (
        "resolved provisional CALL was not rendered with sizing"
    )

    # These remain presentation-only.
    voluntary = [
        action
        for action in hand.actions
        if action.action not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
            "POST_ANTE",
        }
    ]

    assert voluntary == [], (
        "renderer mutated CanonicalHand"
    )

    print(
        "PASS: resolved chronology-pending actions render "
        "with sizing without canonical mutation"
    )


if __name__ == "__main__":
    main()
