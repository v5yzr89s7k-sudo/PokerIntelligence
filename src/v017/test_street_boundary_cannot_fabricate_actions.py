from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/v017/frame_hand_observer.py"


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    target = None

    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "FrameHandObserver"
        ):
            for child in node.body:
                if (
                    isinstance(child, ast.FunctionDef)
                    and child.name == "admit_street_boundary"
                ):
                    target = ast.get_source_segment(
                        source,
                        child,
                    )
                    break

    assert target is not None

    assert "observe_no_commitment(" not in target

    assert (
        "resolve_boundary_completed_actor("
        in target
    )

    assert (
        '"semantic_action":\n'
        '                        None'
        in target
    )

    print(
        "STREET BOUNDARY CANNOT FABRICATE ACTIONS: PASS"
    )


if __name__ == "__main__":
    main()
