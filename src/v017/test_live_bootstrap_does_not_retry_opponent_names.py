import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RUNNER = (
    ROOT
    / "src/v017/run_live_observer.py"
)

SNAPSHOT = (
    ROOT
    / "src/api/table_snapshot_reader_core_v2.py"
)


def function_source(path, name):
    source = path.read_text()
    tree = ast.parse(source)

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
        f"function not found: {name}"
    )


def main():
    runner = function_source(
        RUNNER,
        "build_observer_from_frame",
    )

    snapshot = function_source(
        SNAPSHOT,
        "read_table_snapshot_v2",
    )

    assert (
        "retry_unresolved_names=False"
        in runner
    )

    assert (
        "retry_unresolved_names=True"
        in snapshot
    )

    assert (
        "and retry_unresolved_names"
        in snapshot
    )

    assert (
        "SNAPSHOT_NAME_RETRY_SKIPPED"
        in snapshot
    )

    print(
        "LIVE BOOTSTRAP OPPONENT NAMES CANNOT RETRY: PASS"
    )


if __name__ == "__main__":
    main()
