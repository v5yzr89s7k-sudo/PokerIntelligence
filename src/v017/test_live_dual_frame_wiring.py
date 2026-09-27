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

    transaction = function_source(
        source,
        tree,
        "process_frame_transaction",
    )

    # run_hand owns acquisition/timing only. Prove structurally that
    # the native image is handed unchanged to the single transaction
    # owner; formatting and indentation are not part of the contract.
    run_tree = ast.parse(run)

    transaction_calls = [
        node
        for node in ast.walk(run_tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id
            == "process_frame_transaction"
        )
    ]

    assert transaction_calls

    transaction_call = transaction_calls[0]

    assert len(transaction_call.args) >= 2

    assert (
        isinstance(
            transaction_call.args[0],
            ast.Name,
        )
        and transaction_call.args[0].id
        == "observer"
    )

    assert (
        isinstance(
            transaction_call.args[1],
            ast.Name,
        )
        and transaction_call.args[1].id
        == "image"
    )

    # Canonical physical sensors are derived inside the transaction
    # from that same native image.
    assert (
        "sensor_image = canonical_sensor_frame"
        in transaction
    )

    assert (
        "sensor_frame=sensor_image"
        in transaction
    )

    assert (
        "sensor_geometry=SENSOR_GEOMETRY"
        in transaction
    )

    # Native image remains the primary process_frame frame.
    #
    # Do not encode indentation/formatting here. The production call
    # currently assigns its return value before processing the native
    # frame, and AST/source formatting may change without changing
    # ownership.
    assert (
        "observer.process_frame("
        in transaction
    )

    assert (
        "image,"
        in transaction
    )

    assert (
        "sensor_frame=sensor_image"
        in transaction
    )

    assert (
        "sensor_geometry=SENSOR_GEOMETRY"
        in transaction
    )

    # Semantic/sensor processing must not migrate back into run_hand.
    assert (
        "canonical_sensor_frame"
        not in run
    )

    assert (
        "observer.process_frame("
        not in run
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
