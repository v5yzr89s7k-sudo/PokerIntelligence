"""
v0.16 live-presentation ownership contract.

Normal production semantics must not publish current_hand.txt from canonical
persistence and then overwrite it with an overlay-aware presentation.

CanonicalHandStore.save():
    canonical_hand.json only

CanonicalHandStore.save_live_presentation():
    current_hand.txt only

api_event_state_machine.canonical_save():
    the normal semantic transaction that performs persistence followed by
    exactly one presentation publication.

The old event-to-live writer may remain as an unlaunched legacy utility, but
run_live_observer.py must not start it.
"""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]


def method_node(path, class_name, method_name):
    tree = ast.parse(path.read_text())

    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == class_name
        ):
            for item in node.body:
                if (
                    isinstance(item, ast.FunctionDef)
                    and item.name == method_name
                ):
                    return item

    raise AssertionError(
        f"missing {class_name}.{method_name}"
    )


def function_node(path, function_name):
    tree = ast.parse(path.read_text())

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == function_name
        ):
            return node

    raise AssertionError(
        f"missing function {function_name}"
    )


def calls_in(node):
    result = []

    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue

        try:
            rendered = ast.unparse(child)
        except Exception:
            continue

        result.append(
            (
                child.lineno,
                rendered,
            )
        )

    return result


def main():
    failures = []

    store_path = (
        ROOT
        / "src/state/canonical_hand_store.py"
    )

    state_machine_path = (
        ROOT
        / "src/api/api_event_state_machine.py"
    )

    runner_path = (
        ROOT
        / "src/api/run_live_observer.py"
    )

    save_node = method_node(
        store_path,
        "CanonicalHandStore",
        "save",
    )

    presentation_node = method_node(
        store_path,
        "CanonicalHandStore",
        "save_live_presentation",
    )

    canonical_save_node = function_node(
        state_machine_path,
        "canonical_save",
    )

    save_calls = calls_in(save_node)
    presentation_calls = calls_in(
        presentation_node
    )
    canonical_save_calls = calls_in(
        canonical_save_node
    )

    print(
        "CanonicalHandStore.save calls:",
        save_calls,
    )

    print(
        "save_live_presentation calls:",
        presentation_calls,
    )

    print(
        "canonical_save calls:",
        canonical_save_calls,
    )

    # --------------------------------------------------------------
    # Store.save may write canonical JSON, never text_path.
    # --------------------------------------------------------------

    save_source = ast.unparse(save_node)

    if "self.text_path" in save_source:
        failures.append(
            "CanonicalHandStore.save still writes text_path"
        )

    if "self.json_path" not in save_source:
        failures.append(
            "CanonicalHandStore.save no longer persists json_path"
        )

    # --------------------------------------------------------------
    # save_live_presentation is the physical current_hand writer.
    # --------------------------------------------------------------

    presentation_source = ast.unparse(
        presentation_node
    )

    if "self.text_path" not in presentation_source:
        failures.append(
            "save_live_presentation does not write text_path"
        )

    if "self.json_path" in presentation_source:
        failures.append(
            "save_live_presentation unexpectedly writes json_path"
        )

    # --------------------------------------------------------------
    # canonical_save must persist then choose exactly one publication
    # route. It may call refresh_live_presentation OR direct canonical
    # presentation depending on state, but not through store.save().
    # --------------------------------------------------------------

    canonical_source = ast.unparse(
        canonical_save_node
    )

    required = [
        "CANONICAL_STORE.save(hand)",
        "refresh_live_presentation(state)",
        "CANONICAL_STORE.save_live_presentation",
    ]

    for term in required:
        if term not in canonical_source:
            failures.append(
                f"canonical_save missing transaction component: {term}"
            )

    # --------------------------------------------------------------
    # Runner must not launch the obsolete event-to-live writer.
    # --------------------------------------------------------------

    runner_source = runner_path.read_text()

    forbidden_runner_terms = [
        "api_event_to_live_writer.py",
        "live_hand_event_writer.py",
    ]

    for term in forbidden_runner_terms:
        if term in runner_source:
            failures.append(
                f"runner still references legacy writer: {term}"
            )

    print()
    print("runner legacy writer references: none")

    if failures:
        print()
        print(
            "FAIL: single live-presentation publication gateway"
        )

        for failure in failures:
            print(" -", failure)

        raise SystemExit(1)

    print()
    print(
        "PASS: canonical persistence cannot publish current_hand.txt; "
        "normal semantic publication has one transaction boundary"
    )


if __name__ == "__main__":
    main()
