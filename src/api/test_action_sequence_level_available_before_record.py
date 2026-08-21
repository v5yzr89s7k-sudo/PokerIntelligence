from pathlib import Path
import ast


COORDINATOR = Path(
    "src/api/api_event_coordinator.py"
)


def direct_assignments(function_node, name):
    """
    Return assignments to `name` that belong to this function's
    local scope. Do not count assignments inside nested functions.
    """
    found = []

    def visit(node):
        if (
            node is not function_node
            and isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Lambda,
                ),
            )
        ):
            return

        if isinstance(node, ast.Assign):
            targets = node.targets

        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]

        else:
            targets = []

        for target in targets:
            if (
                isinstance(target, ast.Name)
                and target.id == name
            ):
                found.append(node)

        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(function_node)

    return found


def recorder_calls(function_node):
    found = []

    for node in ast.walk(function_node):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "record"
        ):
            continue

        keywords = {
            item.arg: item.value
            for item in node.keywords
            if item.arg
        }

        value = keywords.get(
            "tournament_level"
        )

        if value is None:
            continue

        found.append(
            (
                node,
                value,
            )
        )

    return found


def main():
    source = COORDINATOR.read_text()
    tree = ast.parse(source)

    main_fn = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "main"
        )
    )

    maybe_hero = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "maybe_read_hero"
        )
    )

    calls = recorder_calls(
        main_fn
    )

    assert calls, (
        "main() must record tournament level metadata"
    )

    record_node, level_expr = calls[0]

    print(
        "main recorder line:",
        record_node.lineno,
    )

    print(
        "recorder tournament_level expression:",
        ast.unparse(level_expr),
    )

    main_level_assignments = direct_assignments(
        main_fn,
        "level",
    )

    hero_level_assignments = direct_assignments(
        maybe_hero,
        "level",
    )

    print(
        "main local level assignments:",
        [
            node.lineno
            for node in main_level_assignments
        ],
    )

    print(
        "maybe_read_hero local level assignments:",
        [
            node.lineno
            for node in hero_level_assignments
        ],
    )

    assert hero_level_assignments, (
        "expected existing hero-event level parsing"
    )

    # This is the actual defect:
    # main() records tournament_level=level but has no local
    # lifecycle owner for that value.
    assert main_level_assignments, (
        "REPRODUCED: main() records "
        "tournament_level=level but level is owned only "
        "by maybe_read_hero()'s separate local scope"
    )

    earliest_main_assignment = min(
        node.lineno
        for node in main_level_assignments
    )

    assert (
        earliest_main_assignment
        < record_node.lineno
    ), (
        "REPRODUCED: main() does not establish tournament "
        "level before ActionSequenceRecorder consumes it"
    )

    print(
        "PASS: main() owns tournament level before recorder use"
    )


if __name__ == "__main__":
    main()
