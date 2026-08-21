from pathlib import Path
import ast


PATH = Path(
    "src/api/api_event_coordinator.py"
)


def main():
    tree = ast.parse(
        PATH.read_text()
    )

    candidates = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not isinstance(func, ast.Attribute):
            continue

        if func.attr != "record":
            continue

        keywords = {
            item.arg
            for item in node.keywords
            if item.arg is not None
        }

        # Identify the ActionSequenceRecorder call by its actual
        # keyword interface.
        required = {
            "frame",
            "changes",
            "state",
            "source_frame",
        }

        if not required.issubset(keywords):
            continue

        candidates.append(
            {
                "lineno": node.lineno,
                "keywords": sorted(keywords),
            }
        )

    print(
        "candidate recorder calls:",
        candidates,
    )

    assert len(candidates) == 1, (
        "expected exactly one "
        "ActionSequenceRecorder call; "
        f"found {len(candidates)}"
    )

    call = candidates[0]

    assert (
        "tournament_level"
        in call["keywords"]
    ), (
        "REPRODUCED: coordinator does not pass "
        "authoritative tournament level into recorder"
    )

    print(
        "PASS: coordinator transports "
        "tournament level into recorder"
    )


if __name__ == "__main__":
    main()
