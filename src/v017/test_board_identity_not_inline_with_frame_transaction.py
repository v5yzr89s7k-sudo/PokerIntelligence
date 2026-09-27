"""
V0.17 board-identity latency ownership contract.

Physical street detection belongs to the real-time frame transaction.

Slow board identity does not.

The frame transaction may queue immutable identity work, but must never
execute read_board_identity() synchronously.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/v017/run_live_observer.py"


def function_node(tree, name):
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return node

    raise AssertionError(
        f"missing function: {name}"
    )


def function_source(source, tree, name):
    node = function_node(tree, name)

    return ast.get_source_segment(
        source,
        node,
    )


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    transaction = function_source(
        source,
        tree,
        "process_frame_transaction",
    )

    assert (
        "FLOP_BOUNDARY_PHYSICAL"
        in transaction
    )

    assert (
        "TURN_BOUNDARY_PHYSICAL"
        in transaction
    )

    assert (
        "RIVER_BOUNDARY_PHYSICAL"
        in transaction
    )

    # RED against current production:
    #
    # slow external identity work must not execute inside the
    # authoritative physical-frame transaction.
    assert (
        "read_board_identity("
        not in transaction
    ), (
        "RED: process_frame_transaction executes blocking "
        "board identity inline"
    )

    # The transaction must still own physical boundary detection.
    assert (
        "boundary_events"
        in transaction
    )

    print(
        "V0.17 BOARD IDENTITY NOT INLINE WITH "
        "FRAME TRANSACTION: PASS"
    )


if __name__ == "__main__":
    main()
