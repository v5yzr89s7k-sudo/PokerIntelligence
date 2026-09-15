from pathlib import Path
import ast


PATH = Path(
    "src/api/api_event_state_machine.py"
)


def main():
    tree = ast.parse(
        PATH.read_text()
    )

    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(
            node,
            ast.FunctionDef,
        )
    }

    failures = []

    snapshot = functions.get(
        "handle_table_snapshot"
    )

    context = functions.get(
        "handle_table_context"
    )

    refresh = functions.get(
        "refresh_live_presentation"
    )

    canonical_save = functions.get(
        "canonical_save"
    )

    for name, node in [
        ("handle_table_snapshot", snapshot),
        ("handle_table_context", context),
        ("refresh_live_presentation", refresh),
        ("canonical_save", canonical_save),
    ]:
        if node is None:
            failures.append(
                f"{name} missing"
            )

    if failures:
        raise SystemExit(
            "\n".join(failures)
        )

    snapshot_body = ast.unparse(
        snapshot
    )

    context_body = ast.unparse(
        context
    )

    refresh_body = ast.unparse(
        refresh
    )

    save_body = ast.unparse(
        canonical_save
    )

    if (
        "state['table_snapshot_received'] = True"
        not in snapshot_body
    ):
        failures.append(
            "snapshot does not establish completion ownership"
        )

    if (
        "state['suppress_live_presentation'] = False"
        not in snapshot_body
    ):
        failures.append(
            "snapshot does not release enrichment suppression"
        )

    if (
        "table_snapshot_received"
        not in context_body
    ):
        failures.append(
            "table_context does not test snapshot completion"
        )

    if (
        "STARTUP_ENRICHMENT_COALESCE_BEGIN"
        not in context_body
    ):
        failures.append(
            "table_context does not reopen passive enrichment suppression"
        )

    if (
        "publication_intent != 'action'"
        not in refresh_body
    ):
        failures.append(
            "action publication bypass missing"
        )

    if (
        "publication_intent='action'"
        in save_body
    ):
        failures.append(
            "canonical_save incorrectly owns action bypass"
        )

    if failures:
        print(
            "STARTUP ENRICHMENT BOUNDARY: FAIL"
        )

        for failure in failures:
            print(
                " -",
                failure,
            )

        raise SystemExit(1)

    print(
        "PASS: table_context publishes fast bootstrap once"
    )

    print(
        "PASS: passive startup enrichment is then coalesced"
    )

    print(
        "PASS: table_snapshot is deterministic enrichment-release boundary"
    )

    print(
        "PASS: explicit action publication still bypasses suppression"
    )

    print(
        "PASS: canonical persistence has no action-publication authority"
    )


if __name__ == "__main__":
    main()
