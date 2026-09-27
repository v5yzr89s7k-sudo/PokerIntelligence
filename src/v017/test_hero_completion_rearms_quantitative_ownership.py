"""
Hero physical action completion must preserve a quantitative evidence
opportunity.

When Hero action buttons disappear while Hero is authoritative, Hero
has objectively acted. If Hero is still below the semantic price, the
action cannot be classified as CHECK from buttons alone.

The physical detector must therefore ensure that existing quantitative
retry ownership remains/re-arms for Hero so a stable post-action stack
can be read before a subsequent street boundary fences later evidence.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/v017/frame_hand_observer.py"


def function_source(
    source,
    tree,
    class_name,
    function_name,
):
    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == class_name
        ):
            for child in node.body:
                if (
                    isinstance(child, ast.FunctionDef)
                    and child.name == function_name
                ):
                    return ast.get_source_segment(
                        source,
                        child,
                    )

    raise AssertionError(
        f"missing {class_name}.{function_name}"
    )


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    process = function_source(
        source,
        tree,
        "FrameHandObserver",
        "process_frame",
    )

    disappeared = process.index(
        '"HERO_ACTION_BUTTONS_DISAPPEARED"'
    )

    stack_loop = process.index(
        "for seat in self.quantitative_seats:"
    )

    assert disappeared < stack_loop

    between = process[
        disappeared:
        stack_loop
    ]

    # RED against current production:
    #
    # Hero button disappearance currently emits physical lifecycle
    # evidence but grants no quantitative retry ownership.
    assert (
        "quantitative_retry_pending"
        in between
    ), (
        "RED: Hero button disappearance does not re-arm "
        "quantitative retry ownership before stack sensing"
    )

    assert (
        "self.hero_seat"
        in between
    ), (
        "RED: Hero completion does not explicitly own Hero "
        "quantitative follow-up"
    )

    print(
        "HERO COMPLETION QUANTITATIVE OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
