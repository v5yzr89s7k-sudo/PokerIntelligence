"""
Structural contract for Hero-completion quantitative retry lifetime.

Hero-completion retry is distinct from generic motion retry:

    generic retry:
        readable OCR completes retry ownership

    Hero-completion retry:
        readable SAME trusted baseline does not prove the resulting
        action stack has appeared yet, so bounded ownership remains

        readable CHANGED stack retires retry ownership and hands the
        transition to normal confirmation / settlement

This test grants no semantic authority to Hero button disappearance.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/v017/frame_hand_observer.py"


def process_source():
    source = PATH.read_text()
    tree = ast.parse(source)

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
                    return ast.get_source_segment(
                        source,
                        child,
                    )

    raise AssertionError(
        "FrameHandObserver.process_frame missing"
    )


def main():
    process = process_source()

    disappeared = process.index(
        '"HERO_ACTION_BUTTONS_DISAPPEARED"'
    )

    stack_loop = process.index(
        "for seat in self.quantitative_seats:"
    )

    bridge = process[
        disappeared:
        stack_loop
    ]

    assert '"reason":' in bridge
    assert '"hero_action_completion"' in bridge

    assert (
        'retry_state.get("reason")'
        in process
    )

    assert (
        "same_baseline_retry = bool("
        in process
    )

    assert (
        '"[QUANTITATIVE_RETRY_BASELINE]"'
        in process
    )

    assert (
        "attempts = int("
        in process
    )

    assert (
        "self.quantitative_retry_max_attempts"
        in process
    )

    # Hero completion still owns evidence only.
    assert "observe_stack_commitment(" not in bridge
    assert "observe_no_commitment(" not in bridge
    assert "admit_quantitative_observation(" not in bridge

    print(
        "HERO COMPLETION SAME-BASELINE "
        "RETRY LIFETIME: PASS"
    )


if __name__ == "__main__":
    main()
