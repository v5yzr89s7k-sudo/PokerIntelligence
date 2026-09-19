"""
V0.17 Pixel Lab PNG-only production transaction runner.

OBSERVER SIDE OF THE ISOLATION WALL.

Allowed inputs:
    * rendered PNG files.

Forbidden:
    * ACR hand parser;
    * ACR truth timeline;
    * ACR pixel renderer;
    * expected actions;
    * expected action frames;
    * generator manifests / truth metadata.

Pixel Lab owns frame acquisition only.

All poker semantics are owned by the same production
process_frame_transaction() used by live ACR.
"""

from pathlib import Path

import cv2

from src.v017.run_live_observer import (
    FrameTransactionState,
    build_observer_from_frame,
    process_frame_transaction,
)


ROOT = Path(__file__).resolve().parents[3]

OBSERVER_INPUT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "real_acr_hand_2826874674"
)


def run():
    paths = tuple(
        sorted(
            OBSERVER_INPUT.glob(
                "frame_*.png"
            )
        )
    )

    if not paths:
        raise RuntimeError(
            f"no observer PNGs: {OBSERVER_INPUT}"
        )

    first_path = paths[0]

    first_image = cv2.imread(
        str(first_path)
    )

    assert first_image is not None, first_path

    observer = build_observer_from_frame(
        first_image,
        first_path,
        hand_id="pixel-simulation",
    )

    if observer is None:
        raise RuntimeError(
            "physical PNG bootstrap unresolved"
        )

    state = FrameTransactionState()

    physical_events = []
    outcomes = []

    print(
        "===== PNG-ONLY PRODUCTION TRANSACTION ====="
    )

    print(
        "input frames =",
        tuple(
            path.name
            for path in paths
        ),
    )

    print(
        "initial next_actor =",
        observer.hand.next_actor,
    )

    print(
        "initial trusted_stacks =",
        observer.trusted_stacks,
    )

    for path in paths:
        frame_id = int(
            path.stem.split("_")[-1]
        )

        image = cv2.imread(
            str(path)
        )

        assert image is not None, path

        before_publications = len(
            observer.publications
        )

        transaction = (
            process_frame_transaction(
                observer,
                image,
                path,
                frame_id,
                state,
            )
        )

        physical_events.extend(
            transaction.events
        )

        outcomes.append(
            (
                frame_id,
                transaction.outcome,
            )
        )

        if transaction.events:
            print()
            print(
                "FRAME",
                frame_id,
            )

            for event in transaction.events:
                print(
                    " physical",
                    event,
                )

        for publication in observer.publications[
            before_publications:
        ]:
            print(
                " publication",
                publication.get("frame"),
                publication.get("street"),
                publication.get("action_count"),
            )

        if transaction.outcome != "CONTINUE":
            print(
                "[PIXEL_TRANSACTION_END]",
                f"frame={frame_id}",
                f"outcome={transaction.outcome}",
            )
            break

    print()
    print(
        "===== OBSERVED HANDENGINE ACTIONS ====="
    )

    for action in observer.hand.semantic_actions():
        print(action)

    print()
    print(
        "trusted_stacks =",
        observer.trusted_stacks,
    )

    print(
        "board =",
        observer.hand.board,
    )

    print(
        "street =",
        observer.hand.street,
    )

    print(
        "hand_complete =",
        observer.hand.hand_complete,
    )

    return {
        "observer": observer,
        "physical_events": tuple(
            physical_events
        ),
        "outcomes": tuple(outcomes),
    }
