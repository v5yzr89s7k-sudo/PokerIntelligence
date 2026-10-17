from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "src/v017/run_live_observer.py"


def main():
    source = RUNNER.read_text()
    tree = ast.parse(source)

    wait_source = None

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "wait_for_hand"
        ):
            wait_source = ast.get_source_segment(
                source,
                node,
            )
            break

    assert wait_source is not None

    assert (
        "acquisition_stack_rows = bootstrap_local_stacks("
        in wait_source
    )

    assert (
        "canonical_image=confirm_image"
        in wait_source
    )

    assert (
        "acquisition_stack_authority"
        in wait_source
    )

    # The returned new-hand stack authority must never be
    # the waiting-period cache.
    return_region = wait_source[
        wait_source.index(
            "acquisition_stack_rows = bootstrap_local_stacks("
        ):
    ]

    assert (
        "participant_freeze.trusted_stacks"
        not in return_region
    )

    print(
        "ACQUISITION FRAME OWNS STARTING STACKS: PASS"
    )


if __name__ == "__main__":
    main()
