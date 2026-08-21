from pathlib import Path
import ast


COORD = Path(
    "src/api/api_event_coordinator.py"
)

STATE_MACHINE = Path(
    "src/api/api_event_state_machine.py"
)

CANONICAL = Path(
    "src/state/canonical_hand.py"
)


def string_literals(tree):
    values = set()

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        ):
            values.add(node.value)

    return values


def main():
    coord_text = COORD.read_text()
    sm_text = STATE_MACHINE.read_text()
    canonical_text = CANONICAL.read_text()

    coord_tree = ast.parse(coord_text)
    sm_tree = ast.parse(sm_text)

    coord_strings = string_literals(
        coord_tree
    )

    sm_strings = string_literals(
        sm_tree
    )

    print(
        "coordinator has initial purpose:",
        "initial" in coord_strings,
    )

    print(
        "coordinator mentions forced baseline:",
        "forced_pot_baseline_bb"
        in coord_text,
    )

    print(
        "state machine handles initial purpose:",
        "initial" in sm_strings,
    )

    print(
        "state machine mentions forced baseline:",
        "forced_pot_baseline_bb"
        in sm_text,
    )

    print(
        "canonical owns starting adjustment:",
        "starting_pot_adjustment_bb"
        in canonical_text,
    )

    assert (
        "forced_pot_baseline_bb"
        in coord_text
    ), (
        "REPRODUCED: initial pot request does not "
        "carry its frozen canonical forced baseline"
    )

    assert (
        "purpose"
        in coord_text
        and "initial" in coord_strings
    ), (
        "REPRODUCED: initial pot request is not "
        "semantically distinguished from ordinary pot reads"
    )

    assert (
        "forced_pot_baseline_bb"
        in sm_text
    ), (
        "REPRODUCED: pot_update does not transport "
        "the frozen forced baseline to the state machine"
    )

    assert (
        "starting_pot_adjustment_bb"
        in canonical_text
    ), (
        "REPRODUCED: CanonicalHand has no durable "
        "starting-pot adjustment owner"
    )

    print(
        "PASS: initial pot baseline has explicit "
        "end-to-end ownership"
    )


if __name__ == "__main__":
    main()
