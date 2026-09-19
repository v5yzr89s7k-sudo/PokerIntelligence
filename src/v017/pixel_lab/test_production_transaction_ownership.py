"""
Pixel Lab must be a deterministic PNG frame source,
not an independent poker-semantic implementation.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

PATH = (
    ROOT
    / "src/v017/pixel_lab/observer_runner.py"
)


def main():
    source = PATH.read_text()
    tree = ast.parse(source)

    assert (
        "process_frame_transaction"
        in source
    )

    forbidden = (
        "observer.process_frame(",
        "StackSettlementGate(",
        "admit_quantitative_observation(",
        "admit_terminal_stack_return(",
        "admit_street_boundary(",
        "_retain_pending_card_disappearance(",
        "reconcile_pending_evidence(",
        "reconcile_pending_card_disappearances(",
        "reconcile_pending_street_boundaries(",
    )

    for token in forbidden:
        assert token not in source, token

    imports = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imports.append(
                node.module or ""
            )

    assert (
        "src.v017.pixel_lab.acr_hand_parser"
        not in imports
    )

    assert (
        "src.v017.pixel_lab.acr_truth_timeline"
        not in imports
    )

    assert (
        "src.v017.pixel_lab.acr_pixel_renderer"
        not in imports
    )

    print(
        "PIXEL LAB -> PRODUCTION TRANSACTION: PASS"
    )
    print(
        "PIXEL LAB DIRECT SEMANTIC ADMISSION: NO"
    )
    print(
        "PIXEL LAB PRIVATE TRUTH IMPORTS: NONE"
    )
    print(
        "V0.17 PIXEL PRODUCTION OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
