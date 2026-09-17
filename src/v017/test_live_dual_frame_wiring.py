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

    native_geometry = json.loads(
        (
            ROOT
            / "config/v017/geometry_maximized.json"
        ).read_text()
    )

    sensor_geometry = json.loads(
        (
            ROOT
            / "config/geometry.json"
        ).read_text()
    )

    assert native_geometry["table_size"] == {
        "width": 3456,
        "height": 2168,
    }

    assert sensor_geometry["table_size"] == {
        "width": 934,
        "height": 696,
    }

    assert (
        'Path("config/geometry.json").read_text()'
        in source
    )

    canonical = function_source(
        source,
        tree,
        "canonical_sensor_frame",
    )

    assert "cv2.resize" in canonical
    assert "SENSOR_FRAME_SIZE" in canonical

    wait = function_source(
        source,
        tree,
        "wait_for_hand",
    )

    assert (
        "canonical_sensor_frame"
        in wait
    )

    assert (
        "hero_cards_visible(\n"
        "            sensor_image,\n"
        "            SENSOR_GEOMETRY,"
        in wait
    )

    run = function_source(
        source,
        tree,
        "run_hand",
    )

    assert (
        "sensor_image = canonical_sensor_frame"
        in run
    )

    assert (
        "sensor_frame=sensor_image"
        in run
    )

    assert (
        "sensor_geometry=SENSOR_GEOMETRY"
        in run
    )

    # Native image must remain the primary process_frame frame.
    assert (
        "observer.process_frame(\n"
        "            image,"
        in run
    )

    main_source = function_source(
        source,
        tree,
        "main",
    )

    assert (
        "if not hero_cards_visible(\n"
        "                sensor_image,\n"
        "                SENSOR_GEOMETRY,"
        in main_source
    )

    print(
        "V0.17 LIVE DUAL-FRAME WIRING: PASS"
    )


if __name__ == "__main__":
    main()
