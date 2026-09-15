"""
Structural contract for v0.16 chronology ownership.

Owned player actions may consume CanonicalHand.players_to_act only through
BettingRoundTracker.consume_owned_action_obligation().

Explicit non-action lifecycle/ownership exceptions are allowed:
- CanonicalHand reset / initialization / street transitions / terminal state
- CanonicalHand deserialization
- observer acquisition frontier
- boundary eligibility reconciliation

Legacy/test-only tracker helpers are not production chronology gateways.
"""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]

PRODUCTION_FILES = [
    ROOT / "src/api/api_event_state_machine.py",
    ROOT / "src/state/action_timeline.py",
    ROOT / "src/state/betting_round_tracker.py",
    ROOT / "src/state/canonical_hand.py",
]

ALLOWED_WRITERS = {
    ("src/state/betting_round_tracker.py", "consume_owned_action_obligation"),
    ("src/state/betting_round_tracker.py", "establish_observer_acquisition_frontier"),

    ("src/state/canonical_hand.py", "reset"),
    ("src/state/canonical_hand.py", "_initialize_players_to_act"),
    ("src/state/canonical_hand.py", "set_board"),
    ("src/state/canonical_hand.py", "add_showdown"),
    ("src/state/canonical_hand.py", "finish"),
    ("src/state/canonical_hand.py", "from_dict"),

    # Eligibility reconciliation is not action consumption. It may only remove
    # players proven inactive/folded/all-in at a historical street boundary.
    ("src/api/api_event_state_machine.py", "handle_boundary_stack_result"),

    # Legacy methods remain in source for historical tests but have no
    # production callers. Their reachability is checked separately below.
    ("src/state/betting_round_tracker.py", "_consume_action_queue"),
    ("src/state/betting_round_tracker.py", "resolve_physically_completed_actor"),
}


def enclosing_function(node, parents):
    current = node

    while current in parents:
        current = parents[current]

        if isinstance(
            current,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            return current.name

    return "<module>"


def players_to_act_writes(path):
    source = path.read_text()
    tree = ast.parse(source)

    parents = {}

    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    writes = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
            ),
        ):
            continue

        try:
            rendered = ast.unparse(node)
        except Exception:
            continue

        # Reads such as:
        # queue = list(hand.players_to_act)
        # are not authority writes.
        targets = []

        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]

        target_text = []

        for target in targets:
            try:
                target_text.append(ast.unparse(target))
            except Exception:
                pass

        def is_players_to_act_target(item):
            return (
                item == "players_to_act"
                or item.endswith(".players_to_act")
            )

        if not any(
            is_players_to_act_target(item)
            for item in target_text
        ):
            continue

        writes.append(
            (
                node.lineno,
                enclosing_function(node, parents),
                rendered,
            )
        )

    return writes


def production_callers(method_name):
    callers = []

    for base in [
        ROOT / "src/api",
        ROOT / "src/state",
    ]:
        for path in base.rglob("*.py"):
            if path.name.startswith("test_"):
                continue

            try:
                tree = ast.parse(path.read_text())
            except Exception:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                name = None

                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr

                if name != method_name:
                    continue

                relative = str(path.relative_to(ROOT))

                callers.append(
                    (
                        relative,
                        node.lineno,
                    )
                )

    return callers


def main():
    failures = []

    print("===== players_to_act WRITE AUTHORITY =====")

    for path in PRODUCTION_FILES:
        relative = str(path.relative_to(ROOT))

        for lineno, function, rendered in players_to_act_writes(path):
            owner = (
                relative,
                function,
            )

            status = (
                "ALLOWED"
                if owner in ALLOWED_WRITERS
                else "UNAUTHORIZED"
            )

            print(
                f"{status}: "
                f"{relative}:{lineno}: "
                f"{function}: "
                f"{rendered}"
            )

            if owner not in ALLOWED_WRITERS:
                failures.append(
                    f"unauthorized players_to_act writer: "
                    f"{relative}:{lineno}:{function}"
                )

    print()
    print("===== LEGACY METHOD REACHABILITY =====")

    for method in [
        "_consume_action_queue",
        "resolve_physically_completed_actor",
    ]:
        callers = production_callers(method)

        print(
            f"{method}: "
            f"production_callers={callers}"
        )

        if callers:
            failures.append(
                f"legacy chronology method is production reachable: "
                f"{method}: {callers}"
            )

    print()
    print("===== GATEWAY REACHABILITY =====")

    gateway_callers = production_callers(
        "consume_owned_action_obligation"
    )

    print(
        "consume_owned_action_obligation:",
        gateway_callers,
    )

    expected_gateway_callers = {
        (
            "src/api/api_event_state_machine.py",
        ),
        (
            "src/state/betting_round_tracker.py",
        ),
    }

    actual_files = {
        (path,)
        for path, _ in gateway_callers
    }

    if actual_files != expected_gateway_callers:
        failures.append(
            "unexpected production gateway caller set: "
            f"{gateway_callers}"
        )

    print()

    if failures:
        print("FAIL: single chronology consumption gateway")
        for failure in failures:
            print(" -", failure)
        raise SystemExit(1)

    print(
        "PASS: one production action-obligation consumption gateway; "
        "lifecycle/acquisition exceptions are explicit"
    )


if __name__ == "__main__":
    main()
