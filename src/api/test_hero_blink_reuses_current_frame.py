from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/api/api_event_coordinator.py"


def main():
    text = PATH.read_text()
    tree = ast.parse(text)

    main_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "main"
    )

    source = ast.get_source_segment(
        text,
        main_node,
    )

    assert source is not None

    assert "blink_frame = cv2.imread" not in source
    assert "blink_frame = cv2.resize" not in source

    assert (
        "hero_blink_buffer.update(\n"
        "                img,"
        in source
    )

    print(
        "PASS Hero blink hot path: "
        "current canonical frame is reused without "
        "disk reread or redundant resize"
    )


if __name__ == "__main__":
    main()
