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
            and node.name == "run_hand"
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
        "frame_id > hero_completion_pending_frame"
        in run
    )
    assert "observe_no_commitment(" in run
    assert "source=buttons_no_commitment" in run

    # Quantitative Hero admission cancels pending completion.
    assert "source=quantitative" in run

    # Hero card disappearance is no longer universally terminal.
    assert "admitted_card_action is not None" in run
    assert "source=hero_cards_disappeared" in run

    print(
        "V0.17 LIVE HERO ACTION LIFECYCLE: PASS"
    )


if __name__ == "__main__":
    main()
