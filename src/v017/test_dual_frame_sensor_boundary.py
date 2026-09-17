from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]

PATH = (
    ROOT
    / "src/v017/frame_hand_observer.py"
)


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    target = None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "process_frame"
        ):
            target = ast.get_source_segment(
                source,
                node,
            )
            break

    assert target is not None

    assert "sensor_frame=None" in target
    assert "sensor_geometry=None" in target

    assert (
        "count_board_cards(\n"
        "                physical_frame,\n"
        "                physical_geometry,"
        in target
    )

    assert (
        "opponent_cards_visible(\n"
        "                    physical_frame,"
        in target
    )

    assert (
        "hero_cards_visible(\n"
        "                physical_frame,\n"
        "                physical_geometry,"
        in target
    )

    # Stack motion must remain on native frame + native geometry.
    assert (
        "measure_stack_motion(\n"
        "                    self.previous_frame,\n"
        "                    frame,\n"
        "                    self.geometry,"
        in target
    )

    assert (
        "self._stack_crop(\n"
        "                        frame,"
        in target
    )

    print(
        "V0.17 DUAL-FRAME SENSOR BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
