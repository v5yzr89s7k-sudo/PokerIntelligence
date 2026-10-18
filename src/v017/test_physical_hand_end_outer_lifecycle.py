import ast
from pathlib import Path


PATH = Path(
    "src/v017/run_live_observer.py"
)


def function_source(source, tree, name):
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return ast.get_source_segment(
                source,
                node,
            )

    raise AssertionError(
        f"missing function: {name}"
    )


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    run_hand = function_source(
        source,
        tree,
        "run_hand",
    )

    main_source = function_source(
        source,
        tree,
        "main",
    )

    assert (
        "return transaction.outcome"
        in run_hand
    )

    assert (
        'hand_outcome == "HAND_COMPLETE"'
        in main_source
    )

    assert (
        'hand_outcome == "PHYSICAL_HAND_ENDED"'
        in main_source
    )

    complete_branch = main_source.index(
        'hand_outcome == "HAND_COMPLETE"'
    )

    physical_branch = main_source.index(
        'hand_outcome == "PHYSICAL_HAND_ENDED"'
    )

    archive_history = main_source.index(
        "archive_completed_hand()"
    )

    validation_archive = main_source.index(
        "archive_live_validation_hand("
    )

    assert (
        complete_branch
        < archive_history
        < physical_branch
    ), (
        "completed-history archive is not "
        "owned exclusively by HAND_COMPLETE"
    )

    assert validation_archive > physical_branch

    assert (
        "[PHYSICAL_HAND_RETIRED]"
        in main_source
    )

    print(
        "RUN_HAND RETURNS TRANSACTION OUTCOME: PASS"
    )
    print(
        "CANONICAL HISTORY REQUIRES HAND_COMPLETE: PASS"
    )
    print(
        "PHYSICAL RETIREMENT SKIPS COMPLETED HISTORY: PASS"
    )
    print(
        "PHYSICAL RETIREMENT PRESERVES DIAGNOSTIC HAND: PASS"
    )
    print(
        "V0.17 OUTER HAND LIFECYCLE: PASS"
    )


if __name__ == "__main__":
    main()
