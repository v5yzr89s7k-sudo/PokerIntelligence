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

    marker = "if board_emitted_this_cycle:"
    assert marker in source

    tail = source.split(marker, 1)[1]
    block = tail.split(
        "# Non-blocking temporal Hero-turn sensor.",
        1,
    )[0]

    # Semantic requirement: same observation cannot continue into Hero-turn
    # processing after board promotion.
    assert "continue" in block

    # Latency requirement: board promotion may not deliberately stall capture.
    assert "time.sleep(" not in block

    print(
        "PASS board-transition fast path: "
        "same-cycle Hero processing is gated by continue "
        "without a 500ms wall-clock stall"
    )


if __name__ == "__main__":
    main()
