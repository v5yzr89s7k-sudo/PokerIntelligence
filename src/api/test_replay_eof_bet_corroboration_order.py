from pathlib import Path
import ast


PATH = Path(
    "src/api/api_event_coordinator.py"
)


def main():
    text = PATH.read_text()
    lines = text.splitlines()
    tree = ast.parse(text)

    main_node = None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "main"
        ):
            main_node = node
            break

    assert main_node is not None

    source = "\n".join(
        lines[
            main_node.lineno - 1:
            main_node.end_lineno
        ]
    )

    marker = (
        'if getattr(\n'
        '                        eof_stack_changes,\n'
        '                        "stack_changed_seats",\n'
        '                        None,\n'
        '                    ):'
    )

    assert marker in source, (
        "EOF stack-change semantic branch missing"
    )

    branch = source.split(
        marker,
        1,
    )[1]

    release = branch.find(
        "release_corroborated_bet_amount_results("
    )

    semantic = branch.find(
        "ingest_eof_stack_semantics("
    )

    assert release >= 0, (
        "REGRESSION: EOF-produced settled stack "
        "ChangeSet bypasses deferred bet corroboration"
    )

    assert semantic >= 0, (
        "EOF semantic ingestion call missing"
    )

    assert release < semantic, (
        "REGRESSION: EOF semantic ingestion occurs "
        "before deferred bet corroboration"
    )

    # Keep the regression local to the same branch. Neither
    # operation should be separated from the EOF stack evidence
    # by the next outer state-save boundary.
    save_state = branch.find(
        "save_state(state)"
    )

    assert save_state >= 0

    assert release < save_state
    assert semantic < save_state

    print(
        "PASS replay EOF settled stack evidence: "
        "bet corroboration precedes semantic ingestion"
    )


if __name__ == "__main__":
    main()
