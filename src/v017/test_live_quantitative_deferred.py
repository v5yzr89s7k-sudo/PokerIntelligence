"""
Structural production contract:
the v0.17 live runner must not admit quantitative OCR into HandEngine
until the live quantitative lane is separately validated.
"""

import ast
from pathlib import Path


def main():
    path = Path(
        "src/v017/run_live_observer.py"
    )

    tree = ast.parse(
        path.read_text()
    )

    target = None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "run_hand"
        ):
            target = node
            break

    assert target is not None

    forbidden = []

    for node in ast.walk(target):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if (
            isinstance(func, ast.Attribute)
            and func.attr
            == "admit_quantitative_observation"
        ):
            forbidden.append(
                func.attr
            )

    assert forbidden == [], forbidden

    print(
        "V0.17 LIVE QUANTITATIVE "
        "SEMANTICS DEFERRED: PASS"
    )


if __name__ == "__main__":
    main()
