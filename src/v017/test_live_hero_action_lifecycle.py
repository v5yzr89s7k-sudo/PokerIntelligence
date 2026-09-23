from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/v017/run_live_observer.py"


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    run = None

    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "process_frame_transaction"
        ):
            run = ast.get_source_segment(
                source,
                node,
            )
            break

    assert run is not None

    assert "HERO_ACTION_BUTTONS_APPEARED" in run
    assert "HERO_ACTION_BUTTONS_DISAPPEARED" in run
    assert "hero_completion_pending_frame" in run
    assert "HERO_COMPLETION_PENDING" in run

    # Button disappearance cannot immediately author CHECK.
    disappeared = run.index(
        '== "HERO_ACTION_BUTTONS_DISAPPEARED"'
    )
    quantitative = run.index(
        '== "STACK_QUANTITATIVE_OBSERVATION"'
    )

    immediate = run[
        disappeared:
        quantitative
    ]

    assert "observe_no_commitment(" not in immediate

    # Later-frame resolution exists.
    assert (
        "frame_id > state.hero_completion_pending_frame"
        in run
    )
    assert "observe_no_commitment(" in run
    assert "source=buttons_no_commitment" in run

    # Quantitative Hero admission cancels pending completion.
    assert "source=quantitative" in run

    # Hero-card disappearance participates in the complete physical
    # frame transaction. It may become an authoritative Hero action
    # after reconciliation; only an unresolved disappearance may use
    # the physical hand-end fallback.
    assert "hero_cards_disappeared_this_frame" in run
    assert "hero_card_action_reconciled" in run
    assert "source=hero_cards_disappeared" in run
    assert (
        "[HERO_DISAPPEARANCE_RETAINED]"
        in run
    )

    assert (
        "[PHYSICAL_HAND_END]"
        not in run
    )

    assert (
        '"PHYSICAL_HAND_END"'
        not in run
    )

    retain = run.index(
        "retain_frame_card_disappearances("
    )
    reconcile = run.index(
        "reconcile_frame_evidence("
    )
    continuation = run.index(
        "[HERO_DISAPPEARANCE_RETAINED]"
    )

    assert (
        retain
        < reconcile
        < continuation
    )

    print(
        "V0.17 LIVE HERO ACTION LIFECYCLE: PASS"
    )


if __name__ == "__main__":
    main()
