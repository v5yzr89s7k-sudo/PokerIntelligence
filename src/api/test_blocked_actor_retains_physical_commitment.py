"""
Regression for September 8 missing CO 4-bet.

Physical action ownership and canonical chronology advancement are
different concerns.

If a later actor's bet region visibly appears while an earlier actor
still has unresolved commitment evidence:

    - chronology may remain blocked;
    - actor_observed must remain pending;
    - BUT the later actor's physical action must immediately acquire
      durable ActionTimeline ownership.

Quantitative settlement later refines that action. It must not decide
whether the already-observed action exists.
"""

from pathlib import Path
import ast


PATH = Path(
    "src/api/api_event_state_machine.py"
)


def function_node(source, name):
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return node

    raise AssertionError(
        f"missing function: {name}"
    )


def calls_in(node, name):
    rows = []

    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue

        func = item.func

        if (
            isinstance(func, ast.Name)
            and func.id == name
        ):
            rows.append(item.lineno)

    return sorted(rows)


def main():
    source = PATH.read_text()

    actor = function_node(
        source,
        "handle_actor_observed",
    )

    physical_calls = calls_in(
        actor,
        "record_physical_live_commitment",
    )

    preserve_calls = calls_in(
        actor,
        "preserve_pending_actor_observation",
    )

    print(
        "physical_commitment_calls:",
        physical_calls,
    )

    print(
        "preserve_pending_calls:",
        preserve_calls,
    )

    assert physical_calls, (
        "record_physical_live_commitment is absent "
        "from handle_actor_observed"
    )

    assert preserve_calls, (
        "pending actor preservation is absent"
    )

    # Find the blocking-gap branch.
    blocking_branch = None

    for node in ast.walk(actor):
        if not isinstance(node, ast.If):
            continue

        segment = (
            ast.get_source_segment(
                source,
                node.test,
            )
            or ""
        )

        if (
            "blocking_gap" in segment
            and "preserve_if_blocked" in segment
        ):
            blocking_branch = node
            break

    assert blocking_branch is not None, (
        "could not locate blocked-later-actor branch"
    )

    branch_source = (
        ast.get_source_segment(
            source,
            blocking_branch,
        )
        or ""
    )

    print()
    print(
        "===== BLOCKED BRANCH ====="
    )
    print(branch_source)

    # This is the actual defect:
    #
    # the branch preserves chronology and returns without first
    # persisting the physically observed commitment.
    assert (
        "record_blocked_hero_physical_commitment"
        in branch_source
    ), (
        "RED: blocked Hero commitment is not delegated "
        "to the durable physical-action owner"
    )

    # Ordering inside the branch matters. The delegated helper
    # must run before the blocked chronology observation is
    # preserved for later replay.
    physical_pos = branch_source.find(
        "record_blocked_hero_physical_commitment"
    )

    preserve_pos = branch_source.find(
        "preserve_pending_actor_observation"
    )

    assert (
        physical_pos >= 0
        and preserve_pos >= 0
        and physical_pos < preserve_pos
    ), (
        "physical commitment ownership must be attempted "
        "before blocked chronology is deferred"
    )

    # Verify the delegated helper itself owns the durable
    # ActionTimeline write rather than merely trusting its name.
    helper_tree = ast.parse(source)

    helper = next(
        node
        for node in helper_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        == "record_blocked_hero_physical_commitment"
    )

    helper_source = (
        ast.get_source_segment(
            source,
            helper,
        )
        or ""
    )

    assert "observe_action" in helper_source, (
        "record_blocked_hero_physical_commitment must "
        "write through ActionTimeline.observe_action"
    )

    print()
    print(
        "PASS: blocked later actor retains physical "
        "ActionTimeline ownership while chronology waits"
    )


if __name__ == "__main__":
    main()
