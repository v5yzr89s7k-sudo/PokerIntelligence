from pathlib import Path
import ast


PATH = Path(
    "src/api/api_event_state_machine.py"
)


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }

    refresh = functions.get(
        "refresh_live_presentation"
    )

    assert refresh is not None

    refresh_body = ast.unparse(refresh)

    assert "publication_intent" in refresh_body
    assert "suppress_live_presentation" in refresh_body
    assert "publication_intent != 'action'" in refresh_body

    required_action_functions = [
        "record_future_street_live_commitment",
        "record_blocked_hero_physical_commitment",
        "record_blocked_opponent_physical_commitment",
        "record_hero_physical_live_commitment",
        "handle_action_observation_rejected",
        "handle_provisional_bet_opened",
        "handle_provisional_bet_closed",
        "handle_actor_observed",
        "handle_inferred_action",
    ]

    direct_action_publishers = []

    for name in required_action_functions:
        node = functions.get(name)
        assert node is not None, name

        body = ast.unparse(node)

        if "refresh_live_presentation" not in body:
            continue

        direct_action_publishers.append(name)

        assert (
            "publication_intent='action'"
            in body
        ), (
            f"{name} has direct presentation publication "
            "without action intent"
        )

    # Bootstrap transaction owners must remain ordinary.
    for name in [
        "handle_table_context",
        "handle_table_snapshot",
    ]:
        body = ast.unparse(
            functions[name]
        )

        assert (
            "publication_intent='action'"
            not in body
        ), (
            f"{name} incorrectly bypasses startup "
            "presentation transaction"
        )

    canonical_save = ast.unparse(
        functions["canonical_save"]
    )

    assert (
        "publication_intent='action'"
        not in canonical_save
    ), (
        "canonical_save gained action authority"
    )

    print(
        "direct action publishers:",
        direct_action_publishers,
    )
    print()
    print(
        "PASS: passive canonical enrichment obeys "
        "presentation suppression"
    )
    print(
        "PASS: explicit action publication bypasses "
        "presentation suppression"
    )
    print(
        "PASS: canonical_save has no action-publication authority"
    )


if __name__ == "__main__":
    main()
