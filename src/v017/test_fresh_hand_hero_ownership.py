from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]

PATH = (
    ROOT
    / "src/v017/run_live_observer.py"
)


def get_function(source, tree, name):
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return ast.get_source_segment(
                source,
                node,
            )

    raise AssertionError(
        f"missing function: {name}"
    )


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    wait = get_function(
        source,
        tree,
        "wait_for_hand",
    )

    bootstrap = get_function(
        source,
        tree,
        "bootstrap_observer",
    )

    main_source = get_function(
        source,
        tree,
        "main",
    )

    # Identity acquisition is explicitly tied to the frame whose
    # canonical Hero sensor is visible.
    assert "clear_confirmed=False" in wait
    assert "[HERO_ACQUISITION]" in wait
    assert "return image, path" in wait

    # Bootstrap forwards the lifecycle ownership fact.
    assert "clear_confirmed=False" in bootstrap
    assert (
        "clear_confirmed=clear_confirmed"
        in bootstrap
    )

    # Initial hand may attach mid-hand; later hands require the
    # main lifecycle to have crossed its clear boundary.
    assert "hand_number > 1" in main_source
    assert "[HERO_CLEAR_CONFIRMED]" in main_source

    # Never use card inequality as ownership authority.
    forbidden = (
        "previous_hero_cards",
        "last_hero_cards",
        "cards !=",
        "hero_cards !=",
    )

    for token in forbidden:
        assert token not in main_source
        assert token not in wait
        assert token not in bootstrap

    print(
        "V0.17 FRESH-HAND HERO OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
