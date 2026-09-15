"""
v0.16 architecture contract.

Observed/inferred voluntary poker actions must reach CanonicalHand through
one projection gateway.

ActionTimeline owns whether an action exists.

The canonical projection gateway owns materialization of that durable
action into CanonicalHand.

No evidence-specific module may independently write a voluntary canonical
action.
"""

from pathlib import Path
import ast

from src.state import action_timeline


ALLOWED_INITIALIZATION_ACTIONS = {
    "POST_ANTE",
    "POST_SMALL_BLIND",
    "POST_BIG_BLIND",
}


def test_projection_gateway_exists():
    gateway = getattr(
        action_timeline,
        "project_action_to_canonical",
        None,
    )

    assert callable(gateway), (
        "RED: ActionTimeline has no single canonical "
        "projection gateway"
    )

    print(
        "PASS: single canonical projection gateway exists"
    )


def _call_name(node):
    func = node.func

    if isinstance(func, ast.Attribute):
        return func.attr

    if isinstance(func, ast.Name):
        return func.id

    return None


def _constant_action_keyword(node):
    for keyword in node.keywords:
        if keyword.arg != "action":
            continue

        value = keyword.value

        if (
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            return value.value.upper()

    return None


def test_boundary_promoter_has_no_canonical_write_authority():
    path = Path(
        "src/state/boundary_result_promoter.py"
    )

    tree = ast.parse(path.read_text())

    hits = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        name = _call_name(node)

        if name in {
            "add_action",
            "add_boundary_action",
        }:
            hits.append(
                (
                    node.lineno,
                    name,
                )
            )

    assert not hits, (
        "RED: boundary_result_promoter still has "
        f"canonical write authority: {hits}"
    )

    print(
        "PASS: boundary promoter has no canonical "
        "write authority"
    )


def test_state_machine_has_no_direct_voluntary_canonical_writer():
    path = Path(
        "src/api/api_event_state_machine.py"
    )

    tree = ast.parse(path.read_text())

    hits = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        name = _call_name(node)

        if name not in {
            "add_action",
            "add_boundary_action",
        }:
            continue

        action = _constant_action_keyword(node)

        # Hand initialization is deliberately outside the
        # observed-voluntary-action ownership contract.
        if action in ALLOWED_INITIALIZATION_ACTIONS:
            continue

        hits.append(
            (
                node.lineno,
                name,
                action,
            )
        )

    assert not hits, (
        "RED: state machine still contains direct "
        "voluntary canonical writers: "
        f"{hits}"
    )

    print(
        "PASS: state machine has no direct voluntary "
        "canonical writer"
    )


def test_betting_round_tracker_has_no_direct_canonical_writer():
    path = Path(
        "src/state/betting_round_tracker.py"
    )

    tree = ast.parse(path.read_text())

    hits = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        name = _call_name(node)

        if name in {
            "add_action",
            "add_boundary_action",
        }:
            hits.append(
                (
                    node.lineno,
                    name,
                )
            )

    assert not hits, (
        "RED: BettingRoundTracker still directly "
        f"writes CanonicalHand actions: {hits}"
    )

    print(
        "PASS: BettingRoundTracker has no direct "
        "canonical writer"
    )


def main():
    tests = [
        test_projection_gateway_exists,
        test_boundary_promoter_has_no_canonical_write_authority,
        test_state_machine_has_no_direct_voluntary_canonical_writer,
        test_betting_round_tracker_has_no_direct_canonical_writer,
    ]

    failures = []

    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures.append(
                (
                    test.__name__,
                    str(exc),
                )
            )

            print()
            print(
                f"EXPECTED RED {test.__name__}"
            )
            print(exc)

    print()
    print("===== ARCHITECTURE FAILURES =====")

    for name, reason in failures:
        print(
            f"{name}: {reason}"
        )

    assert not failures, (
        "single canonical projection ownership "
        f"contract failures: {failures}"
    )

    print()
    print(
        "PASS: voluntary canonical action authority "
        "has one projection gateway"
    )


if __name__ == "__main__":
    main()
