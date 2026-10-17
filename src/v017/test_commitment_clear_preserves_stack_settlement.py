"""
RED regression:

Once same-seat physical commitment has been observed for an active
quantitative retry candidate, disappearance of that bet region must
not cancel the bounded stack-settlement retry lifecycle.

This test is structural and deliberately ignores formatting.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/v017/frame_hand_observer.py"


def is_commitment_seen_test(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and len(node.args) >= 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "commitment_seen"
    )


def contains_retry_pop(node):
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue

        func = child.func

        if (
            isinstance(func, ast.Attribute)
            and func.attr == "pop"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr
            == "quantitative_retry_pending"
        ):
            return True

    return False


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    process_frame = None

    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "FrameHandObserver"
        ):
            for child in node.body:
                if (
                    isinstance(child, ast.FunctionDef)
                    and child.name == "process_frame"
                ):
                    process_frame = child
                    break

    assert process_frame is not None

    destructive_branches = []

    for node in ast.walk(process_frame):
        if not isinstance(node, ast.If):
            continue

        if (
            is_commitment_seen_test(node.test)
            and contains_retry_pop(node)
        ):
            destructive_branches.append(
                node.lineno
            )

    assert not destructive_branches, (
        "RED: commitment-clear path destroys "
        "quantitative retry ownership at lines "
        f"{destructive_branches}"
    )

    print(
        "COMMITMENT CLEAR PRESERVES STACK SETTLEMENT: PASS"
    )


if __name__ == "__main__":
    main()
