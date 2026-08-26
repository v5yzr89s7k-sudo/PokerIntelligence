"""
RED contract.

A quantitative inferred_action may not cross an earlier unresolved
same-hand/same-street provisional bet.

The state machine must preserve the later quantitative event until
the provisional owner resolves. Only then may normal tracker
classification run against the corrected betting state.
"""

from pathlib import Path


def main():
    source = Path(
        "src/api/api_event_state_machine.py"
    ).read_text()

    start = source.index(
        "def handle_inferred_action("
    )

    end = source.index(
        "\n\n",
        source.index(
            "return state",
            start,
        ) + len("return state"),
    )

    # Use a generous function slice because handle_inferred_action is large.
    region = source[start:start + 18000]

    print(
        "===== HANDLE_INFERRED_ACTION BARRIER REGION ====="
    )

    print(
        region[:9000]
    )

    assert (
        "unresolved_provisional_bets"
        in region
    ), (
        "RED: handle_inferred_action does not consult "
        "unresolved provisional bet ownership before "
        "quantitative tracker ingestion"
    )

    # The barrier must preserve rather than discard the later event.
    assert (
        "pending_inferred_actions"
        in region
    ), (
        "RED: quantitative event has no preservation path"
    )

    close_start = source.index(
        "def handle_provisional_bet_closed("
    )

    close_region = source[
        close_start:
        close_start + 5000
    ]

    print()
    print(
        "===== PROVISIONAL CLOSE REGION ====="
    )

    print(
        close_region
    )

    assert (
        "pending_inferred_actions"
        in close_region
    ), (
        "RED: provisional close does not retry preserved "
        "quantitative inferred actions"
    )

    print()
    print(
        "PASS: provisional ownership blocks and later "
        "releases quantitative action publication"
    )


if __name__ == "__main__":
    main()
