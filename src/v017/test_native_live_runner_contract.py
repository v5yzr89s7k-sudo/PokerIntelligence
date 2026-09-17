from pathlib import Path
import ast
import json


ROOT = Path(__file__).resolve().parents[2]

RUNNER = (
    ROOT
    / "src/v017/run_live_observer.py"
)

GEOMETRY = (
    ROOT
    / "config/v017/geometry_maximized.json"
)


def main():
    source = RUNNER.read_text()
    tree = ast.parse(source)

    geometry = json.loads(
        GEOMETRY.read_text()
    )

    assert geometry["table_size"] == {
        "width": 3456,
        "height": 2168,
    }

    assert (
        'config/v017/geometry_maximized.json'
        in source
    )

    assert (
        "read_stack_native_fast"
        in source
    )

    assert (
        "v0.17 native frame size mismatch"
        in source
    )

    # The live runner must no longer downsample its
    # primary frame to canonical 934x696.
    capture = None

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "capture_image"
        ):
            capture = ast.get_source_segment(
                source,
                node,
            )
            break

    assert capture is not None

    assert "cv2.resize" not in capture
    assert "(934, 696)" not in capture

    # Dealer detector remains isolated in its own legacy
    # implementation; do not patch that module here.
    dealer_source = (
        ROOT
        / "src/vision/dealer_detector.py"
    ).read_text()

    assert "to_canonical_frame" in dealer_source
    assert "load_geometry()" in dealer_source

    print(
        "V0.17 NATIVE LIVE RUNNER CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
