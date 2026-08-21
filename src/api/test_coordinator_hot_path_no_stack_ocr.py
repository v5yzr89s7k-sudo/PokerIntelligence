from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/api/api_event_coordinator.py"


FORBIDDEN_DIRECT_CALLS = {
    "read_stack",
    "read_stack_independent_consensus",
    "prechange_stack_observation",
    "retry_one_startup_stack",
    "enrich_stack_change_measurements",
}


def function_node(tree, name):
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ) and node.name == name:
            return node

    raise AssertionError(f"function not found: {name}")


def direct_calls(node):
    calls = []

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue

        fn = child.func

        if isinstance(fn, ast.Name):
            calls.append((fn.id, child.lineno))
        elif isinstance(fn, ast.Attribute):
            calls.append((fn.attr, child.lineno))

    return calls


def main():
    text = PATH.read_text()
    tree = ast.parse(text)

    main_node = function_node(tree, "main")

    calls = direct_calls(main_node)

    forbidden = [
        (name, lineno)
        for name, lineno in calls
        if name in FORBIDDEN_DIRECT_CALLS
    ]

    print("=" * 72)
    print("COORDINATOR HOT-PATH STACK OCR CONTRACT")
    print("=" * 72)

    if forbidden:
        print()
        print("FORBIDDEN synchronous calls still in main():")

        for name, lineno in forbidden:
            print(
                f"  line {lineno}: {name}()"
            )

        raise AssertionError(
            "coordinator capture loop still owns "
            "synchronous stack OCR/recovery"
        )

    print()
    print(
        "PASS: coordinator main() contains no direct "
        "stack OCR/recovery calls"
    )


if __name__ == "__main__":
    main()
