"""
September 8 live regression.

Ground truth:
    seat_top produced bet_region_appeared
    seat_top had no stack_changed evidence
    seat_top later completed via opponent_card_disappearance

The visual bet-region transition was therefore not sufficient evidence
to author a durable betting action.

Contract:
    bet_region_appeared may open provisional/quantitative acquisition,
    but without independent commitment corroboration it may not create
    a durable opponent BET_OR_RAISE/COMMITMENT ActionTimeline owner.
"""

from pathlib import Path
import ast


PATH = Path(
    "src/api/api_event_state_machine.py"
)


def get_function(source, name):
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return node

    raise AssertionError(
        f"missing function {name}"
    )


def main():
    source = PATH.read_text()

    fn = get_function(
        source,
        "record_physical_live_commitment",
    )

    body = (
        ast.get_source_segment(
            source,
            fn,
        )
        or ""
    )

    print(
        "===== record_physical_live_commitment ====="
    )
    print(body)

    # Current defect:
    #
    # source=bet_region_appeared +
    # commitment_visible=True
    #
    # is enough to call observe_action() and create durable
    # semantic ownership, even when no independent commitment
    # evidence exists.
    assert (
        "bet_region_appeared" not in body
        or "observe_action" not in body
    ), (
        "RED: uncorroborated bet_region_appeared "
        "can directly author durable opponent action"
    )

    print(
        "PASS: raw bet-region appearance has no "
        "independent durable action authority"
    )


if __name__ == "__main__":
    main()
