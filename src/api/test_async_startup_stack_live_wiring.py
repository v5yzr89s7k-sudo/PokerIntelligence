from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
COORDINATOR = ROOT / "src/api/api_event_coordinator.py"


def function_node(tree, name):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return node

    raise AssertionError(
        f"function not found: {name}"
    )


def direct_calls(node, name):
    found = []

    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == name
        ):
            found.append(child.lineno)

    return found


def main():
    text = COORDINATOR.read_text()
    tree = ast.parse(text)

    main_node = function_node(
        tree,
        "main",
    )

    async_queue = direct_calls(
        main_node,
        "queue_one_startup_stack_async",
    )

    async_consume = direct_calls(
        main_node,
        "consume_startup_stack_worker_results",
    )

    legacy_retry = direct_calls(
        main_node,
        "retry_one_startup_stack",
    )

    print(
        "queue_one_startup_stack_async calls in main:",
        async_queue,
    )

    print(
        "consume_startup_stack_worker_results calls in main:",
        async_consume,
    )

    print(
        "retry_one_startup_stack calls in main:",
        legacy_retry,
    )

    assert async_queue, (
        "BUG: live coordinator never queues asynchronous "
        "startup-stack baseline work"
    )

    assert async_consume, (
        "BUG: live coordinator never consumes asynchronous "
        "startup-stack baseline results"
    )

    assert not legacy_retry, (
        "BUG: synchronous startup stack OCR remains on "
        "the live coordinator path"
    )

    print()
    print(
        "PASS: live startup-stack recovery is worker-owned "
        "and non-blocking"
    )


if __name__ == "__main__":
    main()
