from pathlib import Path
import ast


PATH = Path(
    "src/api/api_event_state_machine.py"
)

SOURCE = PATH.read_text()
TREE = ast.parse(SOURCE)


def function(name):
    return next(
        node
        for node in ast.walk(TREE)
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        )
    )


def calls_in(fn):
    rows = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if isinstance(func, ast.Attribute):
            receiver = (
                ast.get_source_segment(
                    SOURCE,
                    func.value,
                )
                or ""
            )
            name = func.attr

        elif isinstance(func, ast.Name):
            receiver = ""
            name = func.id

        else:
            continue

        rows.append(
            (
                node.lineno,
                receiver,
                name,
            )
        )

    return sorted(rows)


def main():
    fn = function(
        "handle_inferred_action"
    )

    calls = calls_in(fn)

    interesting = [
        row
        for row in calls
        if row[2] in {
            "ingest",
            "resolve_inferred_action",
            "observe_action",
            "refine_action",
            "project_action_to_canonical",
            "apply_resolved_action",
        }
    ]

    print(
        "quantitative_orchestration_calls:",
        interesting,
    )

    tracker_ingest = [
        row
        for row in interesting
        if (
            row[1] == "tracker"
            and row[2] == "ingest"
        )
    ]

    resolver = [
        row
        for row in interesting
        if (
            row[1] == "tracker"
            and row[2]
            == "resolve_inferred_action"
        )
    ]

    apply = [
        row
        for row in interesting
        if (
            row[1] == "tracker"
            and row[2]
            == "apply_resolved_action"
        )
    ]

    projection = [
        row
        for row in interesting
        if row[2]
        == "project_action_to_canonical"
    ]

    refinement = [
        row
        for row in interesting
        if row[2] == "refine_action"
    ]

    assert tracker_ingest == [], (
        "RED: production quantitative handler "
        "still delegates semantic existence and "
        "canonical mutation to tracker.ingest(): "
        f"{tracker_ingest}"
    )

    assert len(resolver) == 1, (
        "RED: production quantitative handler "
        "does not use the pure betting resolver"
    )

    assert len(refinement) >= 1, (
        "RED: quantitative settlement does not "
        "refine the durable ActionTimeline owner"
    )

    assert len(projection) == 1, (
        "RED: production quantitative handler "
        "does not use the single canonical "
        "projection gateway"
    )

    assert len(apply) == 1, (
        "RED: production quantitative handler "
        "does not use the mutation-only tracker "
        "application API"
    )

    ordered = {
        "resolve": resolver[0][0],
        "refine": refinement[0][0],
        "project": projection[0][0],
        "apply": apply[0][0],
    }

    print(
        "ordered_gateway:",
        ordered,
    )

    assert (
        ordered["resolve"]
        < ordered["refine"]
        < ordered["project"]
        < ordered["apply"]
    ), (
        "quantitative ownership pipeline is "
        "out of order"
    )

    print(
        "PASS: quantitative settlement uses "
        "resolver -> ActionTimeline refinement -> "
        "canonical projection -> tracker application"
    )


if __name__ == "__main__":
    main()
