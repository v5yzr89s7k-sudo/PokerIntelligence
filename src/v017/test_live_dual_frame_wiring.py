from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parents[2]

RUNNER = (
    ROOT
    / "src/v017/run_live_observer.py"
)


def function_source(source, tree, name):
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
    source = RUNNER.read_text()
    tree = ast.parse(source)

    geometry = json.loads(
        (
            ROOT
            / "config/v017/geometry_maximized.json"
        ).read_text()
    )

    assert geometry["table_size"] == {
        "width": 3456,
        "height": 2168,
    }

    assert 'Path("config/geometry.json")' not in source
    assert "canonical_sensor_frame" not in source
    assert "SENSOR_GEOMETRY" not in source
    assert "SENSOR_FRAME_SIZE" not in source

    wait = function_source(
        source,
        tree,
        "wait_for_hand",
    )

    transaction = function_source(
        source,
        tree,
        "process_frame_transaction",
    )

    main_source = function_source(
        source,
        tree,
        "main",
    )

    assert "hero_cards_visible(" in wait
    assert "image," in wait
    assert "GEOMETRY," in wait

    assert "observer.process_frame(" in transaction
    assert "sensor_frame=" not in transaction
    assert "sensor_geometry=" not in transaction

    assert "hero_cards_visible(" in main_source
    assert "image," in main_source
    assert "GEOMETRY," in main_source

    print("ONE PHYSICAL FRAME: PASS")
    print("3456x2168 GEOMETRY AUTHORITY: PASS")
    print("DUAL-FRAME WIRING: ABSENT")
    print("V0.17 FULL-SIZE LIVE WIRING: PASS")


if __name__ == "__main__":
    main()
