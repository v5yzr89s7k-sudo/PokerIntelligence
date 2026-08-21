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

    block = function_source(
        text,
        "queue_stack_worker_request",
    )

    required = [
        'str(purpose or "settled") == "settled"',
        'not state.get("hand_token")',
        '"[STACK_WORKER] skip unowned settled request "',
        '"reason=no_hand_token"',
    ]

    missing = [
        item
        for item in required
        if item not in block
    ]

    assert not missing, missing

    # Transport must not independently reject WAITING if a caller still owns
    # a valid hand token. Phase interpretation belongs to higher-level
    # lifecycle logic.
    guard_start = block.index(
        'str(purpose or "settled") == "settled"'
    )

    guard_end = block.index(
        "request_id = uuid.uuid4().hex"
    )

    guard = block[
        guard_start:guard_end
    ]

    assert (
        '== "WAITING"'
        not in guard
    ), (
        "settled transport incorrectly treats WAITING "
        "as equivalent to missing hand ownership"
    )

    print(
        "PASS settled stack ownership guard: "
        "tokenless settled work is rejected without "
        "changing existing phase semantics"
    )


if __name__ == "__main__":
    main()
