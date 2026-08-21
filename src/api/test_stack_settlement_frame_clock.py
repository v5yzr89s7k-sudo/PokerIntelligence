from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]

PATH = ROOT / "src/api/api_event_coordinator.py"


def function_source(text, name):
    tree = ast.parse(text)
    lines = text.splitlines()

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return "\n".join(
                lines[node.lineno - 1:node.end_lineno]
            )

    raise AssertionError(
        f"function not found: {name}"
    )


def main():
    text = PATH.read_text()

    enrich = function_source(
        text,
        "enrich_stack_change_measurements",
    )

    main_block = function_source(
        text,
        "main",
    )

    assert (
        "float(frame_ts)"
        in enrich
    )

    assert (
        "if frame_ts is not None"
        in enrich
    )

    assert (
        "else time.time()"
        in enrich
    )

    assert (
        "replay.first_recorded_ts"
        in main_block
    )

    assert (
        "replay.current_recorded_elapsed"
        in main_block
    )

    assert (
        "frame_ts=("
        in main_block
    )

    print(
        "PASS stack settlement frame clock: "
        "live retains wall time while replay uses "
        "the recorded frame timeline"
    )


if __name__ == "__main__":
    main()
