from pathlib import Path
import ast

from src.state.betting_round_tracker import (
    BettingRoundTracker,
)
from src.state.canonical_hand import (
    CanonicalHand,
)


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="skipped-action-no-authority",
        players=[
            {
                "seat": "utg",
                "name": "UTG",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "hj",
                "name": "HJ",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BB",
        positions={
            "utg": "UTG",
            "hj": "HJ",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"
    hand.players_to_act = [
        "utg",
        "hj",
        "hero",
    ]

    return hand


def test_runtime_behavior():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    before_actions = list(
        hand.actions
    )

    resolved = (
        tracker.advance_to_observed_actor(
            "hj",
            ts=2.0,
        )
    )

    assert resolved == [], (
        "skipping past UTG must not fabricate "
        "a canonical predecessor action"
    )

    assert hand.actions == before_actions, (
        "chronology synchronization mutated "
        "canonical action history"
    )

    assert (
        hand.players["utg"].folded
        is False
    )

    assert (
        hand.players["utg"].active
        is True
    )

    assert hand.players_to_act == [
        "utg",
        "hj",
        "hero",
    ], (
        "later actor observation must not consume the unresolved "
        "UTG betting obligation"
    )

    print(
        "PASS: skipped predecessor remains "
        "unknown rather than fabricated"
    )


def test_no_direct_writer():
    path = Path(
        "src/state/betting_round_tracker.py"
    )

    source = path.read_text()
    tree = ast.parse(source)

    fn = next(
        node
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "_infer_skipped_actions"
        )
    )

    writes = []

    for node in ast.walk(fn):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        func = node.func

        if (
            isinstance(
                func,
                ast.Attribute,
            )
            and func.attr in {
                "add_action",
                "add_boundary_action",
            }
        ):
            writes.append(
                (
                    node.lineno,
                    func.attr,
                )
            )

    assert writes == [], (
        "RED: skipped-action inference "
        "still owns canonical writes: "
        f"{writes}"
    )

    print(
        "PASS: skipped chronology has "
        "no canonical write authority"
    )


def main():
    test_runtime_behavior()
    test_no_direct_writer()

    print(
        "PASS skipped chronology "
        "single-owner contract"
    )


if __name__ == "__main__":
    main()
