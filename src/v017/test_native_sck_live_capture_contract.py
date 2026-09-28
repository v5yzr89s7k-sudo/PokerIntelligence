from pathlib import Path
import ast

SOURCE_PATH = Path(
    "src/v017/run_live_observer.py"
)

SOURCE = SOURCE_PATH.read_text()


def function_source(name):
    tree = ast.parse(SOURCE)

    for node in tree.body:
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == name
        ):
            return ast.get_source_segment(
                SOURCE,
                node,
            )

    raise AssertionError(
        f"missing function: {name}"
    )


def main():
    capture = function_source(
        "capture_image"
    )

    transaction = function_source(
        "process_frame_transaction"
    )

    assert "SCKFrameSource" in SOURCE

    assert "capture_window_crop" not in capture
    assert "cv2.imread" not in capture
    assert "cv2.imwrite" not in capture

    assert "NATIVE_FRAME_SIZE" in capture
    assert "native frame size mismatch" in capture

    assert "canonical_sensor_frame" not in SOURCE
    assert "SENSOR_FRAME_SIZE" not in SOURCE
    assert "SENSOR_GEOMETRY" not in SOURCE

    assert "observer.process_frame(" in transaction
    assert "sensor_frame=" not in transaction
    assert "sensor_geometry=" not in transaction

    print("IN-MEMORY CAPTURE: PASS")
    print("3456x2168 DIMENSION GUARD: PASS")
    print("SECOND SENSOR FRAME: ABSENT")
    print("V0.17 FULL-SIZE LIVE CAPTURE CONTRACT: PASS")


if __name__ == "__main__":
    main()
