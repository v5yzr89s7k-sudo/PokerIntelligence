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
    canonical_sensor_frame,
    SENSOR_GEOMETRY,
    GEOMETRY,
    bootstrap_local_stacks,
    crop_geometry_region,
    read_stack_native_fast,
)

from src.v017.frame_hand_observer import (
    hero_cards_visible,
)

from src.v017.native_seat_occupancy import (
    native_occupied_seats,
)

from src.v017.participant_freeze import (
    ParticipantFreeze,
)
from src.v017.live_product_sink import (
    publish_current_hand_text,
)


ROOT = Path(__file__).resolve().parents[3]

OBSERVER_INPUT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "real_acr_hand_2826874674"
)



def run(
    observer_input=OBSERVER_INPUT,
    *,
    publish_live_product=False,
    publication_dir=None,
):
    observer_input = Path(observer_input)

    if publication_dir is not None:
        publication_dir = Path(
            publication_dir
        )
        publication_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    paths = tuple(
        sorted(
            observer_input.glob(
                "frame_*.png"
            )
        )
    )

    if not paths:
        raise RuntimeError(
            f"no observer PNGs: {observer_input}"
        )

    observer = None
    acquisition_index = None

    participant_freeze = ParticipantFreeze(
        stable_required=3
    )

    for index, path in enumerate(paths):
        image = cv2.imread(
            str(path)
        )
        assert image is not None, path

        observed_participants = (
            native_occupied_seats(
                image,
                GEOMETRY,
            )
        )

        frozen_participants = (
            participant_freeze.observe(
                observed_participants
            )
        )

        sensor_image = (
            canonical_sensor_frame(
                image
            )
        )

        visible = hero_cards_visible(
            sensor_image,
            SENSOR_GEOMETRY,
        )

        if not visible:
            stack_rows = bootstrap_local_stacks(
                canonical_image=image,
                frozen_participants=
                    observed_participants,
                geometry=GEOMETRY,
                crop_geometry_region=
                    crop_geometry_region,
                stack_reader=
                    read_stack_native_fast,
            )

            participant_freeze.observe_stack_authority(
                stack_rows,
                frame=path.name,
            )

            continue

        print(
            "[PIXEL_ACQUISITION]",
            f"frame={path.name}",
            "hero_cards_visible=True",
        )

        if frozen_participants is None:
            frozen_participants = tuple(
                observed_participants
            )

            print(
                "[PIXEL_PARTICIPANT_FREEZE_FALLBACK]",
                f"seats={frozen_participants}",
            )
        else:
            print(
                "[PIXEL_PARTICIPANT_FREEZE]",
                f"seats={frozen_participants}",
                f"streak={participant_freeze.streak}",
            )

        observer = build_observer_from_frame(
            image,
            path,
            hand_id="pixel-simulation",
            frozen_participants=
                frozen_participants,
            frozen_stack_authority=
                participant_freeze.trusted_stacks,
        )

        if observer is None:
            raise RuntimeError(
                "physical PNG bootstrap unresolved "
                "after physical Hero-card acquisition"
            )

        acquisition_index = index
        break

    if (
        observer is None
        or acquisition_index is None
    ):
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
        "acquisition_frame =",
        paths[acquisition_index].name,
    )

    print(
        "initial next_actor =",
        observer.hand.next_actor,
    )

    print(
        "initial trusted_stacks =",
        observer.trusted_stacks,
    )

    # Acquisition frame establishes the physical baseline.
    # Transactions begin with the following frame.
    for path in paths[
        acquisition_index + 1:
    ]:
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

            if publish_live_product:
                publish_current_hand_text(
                    publication["text"]
                )

            if publication_dir is not None:
                publication_index = len(
                    tuple(
                        publication_dir.glob(
                            "*_current_hand.txt"
                        )
                    )
                ) + 1

                frame_label = str(
                    publication.get(
                        "frame",
                        "unknown",
                    )
                )

                publication_path = (
                    publication_dir
                    / (
                        f"{publication_index:03d}_"
                        f"frame_{frame_label}_"
                        "current_hand.txt"
                    )
                )

                publication_path.write_text(
                    publication["text"],
                    encoding="utf-8",
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
