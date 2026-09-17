"""
Structural ownership contract:
Hero-card disappearance must terminate the current live hand loop.
"""

import ast
from pathlib import Path


def main():
    path = Path(
        "src/v017/run_live_observer.py"
    )

    source = path.read_text()

    assert (
        "[PHYSICAL_HAND_END]"
        in source
    )

    tree = ast.parse(source)

    target = None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "run_hand"
        ):
            target = node
            break

    assert target is not None

    found = False

    for node in ast.walk(target):
        if not isinstance(node, ast.If):
            continue

        segment = ast.get_source_segment(
            source,
            node,
        ) or ""

        if (
            "HERO_CARDS_DISAPPEARED_PHYSICAL"
            in segment
            and "[PHYSICAL_HAND_END]"
            in segment
            and any(
                isinstance(child, ast.Return)
                for child
                in ast.walk(node)
            )
        ):
            found = True
            break

    assert found

    print(
        "V0.17 PHYSICAL HAND OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
