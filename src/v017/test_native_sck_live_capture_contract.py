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

    sensor = function_source(
        "canonical_sensor_frame"
    )

    run_hand = function_source(
        "run_hand"
    )

    print(
        "===== NATIVE CAPTURE OWNERSHIP ====="
    )

    assert "SCKFrameSource" in SOURCE, (
        "v0.17 has no persistent SCK frame source"
    )

    assert "capture_window_crop" not in capture, (
        "capture_image still uses legacy "
        "screencapture/PNG acquisition"
    )

    assert "cv2.imread" not in capture, (
        "capture_image still decodes a materialized "
        "PNG from disk"
    )

    assert "cv2.imwrite" not in capture, (
        "normal capture path must not materialize "
        "every live frame"
    )

    print(
        "NORMAL LIVE CAPTURE IS IN-MEMORY: PASS"
    )

    print()
    print(
        "===== NATIVE FRAME CONTRACT ====="
    )

    assert "NATIVE_FRAME_SIZE" in capture

    assert (
        "native frame size mismatch"
        in capture
    )

    print(
        "NATIVE DIMENSION GUARD: PASS"
    )

    print()
    print(
        "===== DUAL-FRAME CONTRACT ====="
    )

    assert "cv2.resize" in sensor
    assert "SENSOR_FRAME_SIZE" in sensor

    assert "capture_image(" in run_hand
    assert "process_frame_transaction(" in run_hand

    print(
        "NATIVE -> CANONICAL DERIVATION: PASS"
    )

    print(
        "RUN_HAND USES CAPTURE OWNER: PASS"
    )

    print()
    print(
        "V0.17 NATIVE SCK LIVE CAPTURE CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
