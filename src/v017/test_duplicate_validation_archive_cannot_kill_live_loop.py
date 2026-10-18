"""
Diagnostic validation archival must never own production liveness.

A duplicate diagnostic hand directory may occur across independent
application launches because hand numbering restarts. Failure to
archive diagnostics must not terminate the live observer.
"""

import ast
from pathlib import Path


PATH = Path("src/v017/run_live_observer.py")


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

    raise AssertionError(name)


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    main_source = function_source(
        source,
        tree,
        "main",
    )

    required = (
        "archive_live_validation_hand(",
        "[LIVE_VALIDATION_ARCHIVE_FAILED]",
        "except RuntimeError as exc:",
        "[NEXT_HAND] waiting...",
    )

    for token in required:
        assert token in main_source, (
            "RED: diagnostic validation archive "
            "failure can still terminate live loop; "
            f"missing={token!r}"
        )

    archive_call = main_source.index(
        "archive_live_validation_hand("
    )

    failure_marker = main_source.index(
        "[LIVE_VALIDATION_ARCHIVE_FAILED]"
    )

    next_hand = main_source.index(
        "[NEXT_HAND] waiting..."
    )

    assert (
        archive_call
        < failure_marker
        < next_hand
    )

    print(
        "DUPLICATE VALIDATION ARCHIVE CANNOT "
        "KILL LIVE LOOP: PASS"
    )


if __name__ == "__main__":
    main()
