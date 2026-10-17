from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "src/v017/run_live_observer.py"


def main():
    source = RUNNER.read_text()
    tree = ast.parse(source)

    target = None

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "build_observer_from_frame"
        ):
            target = ast.get_source_segment(
                source,
                node,
            )
            break

    assert target is not None

    assert "frozen_stack_authority" in target
    assert "acquisition_stacks = dict(" in target

    stack_block = target[
        target.index("acquisition_stacks = dict("):
        target.index("hero_cards = read_hero_identity(")
    ]

    assert "snapshot_players.get(" not in stack_block
    assert '"stack_bb": authority.get(' in stack_block
    assert '"source=acquisition_frame"' in stack_block

    print(
        "SNAPSHOT CANNOT OVERWRITE ACQUISITION STACKS: PASS"
    )


if __name__ == "__main__":
    main()
