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
import hashlib
import json
from contextlib import nullcontext
from unittest.mock import patch
import time

import cv2


from src.v017.run_live_observer import (
    FrameTransactionState,
    build_observer_from_frame,
    process_frame_transaction,
    finalize_async_board_identity_result,
    apply_async_board_identity_result,
    submit_next_pending_board_boundary,
    GEOMETRY,
    bootstrap_local_stacks,
    crop_geometry_region,
    read_stack_native_fast,
)

from src.v017.frame_hand_observer import (
    hero_cards_visible,
)

from src.v017.native_dealer_detector import detect_native_dealer

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




def load_replay_identity_snapshot(frame_path, fixture_path, seats):
    fixture = json.loads(Path(fixture_path).read_text())

    assert fixture["schema_version"] == 1

    image = cv2.imread(str(frame_path))
    assert image is not None

    assert [image.shape[1], image.shape[0]] == fixture["frame_size"]

    digest = hashlib.sha256(
        Path(frame_path).read_bytes()
    ).hexdigest()

    assert digest == fixture["acquisition_frame_sha256"], (
        "REPLAY IDENTITY FRAME HASH MISMATCH"
    )

    rows = fixture["players"]
    fixture_seats = [row["seat"] for row in rows]

    assert len(fixture_seats) == len(set(fixture_seats))
    assert set(fixture_seats) == set(seats), (
        "REPLAY IDENTITY SEAT SET MISMATCH"
    )

    players = [
        {
            "seat": row["seat"],
            "name": row.get("name") or "",
            "is_hero": row["seat"] == "hero",
        }
        for row in rows
    ]

    return {
        "dealer_button_seat": "",
        "players": players,
        "occupied_seats": list(seats),
        "confidence": None,
        "source": "hash_verified_replay_fixture",
    }, {"total_ms": 0.0}


def run(
    observer_input=OBSERVER_INPUT,
    *,
    publish_live_product=False,
    publication_dir=None,
    identity_fixture=None,
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
        visible = hero_cards_visible(
            image,
            GEOMETRY,
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

        first_dealer = detect_native_dealer(image)

        if index + 1 >= len(paths):
            raise RuntimeError(
                "dealer confirmation requires another frame"
            )

        confirm_image = cv2.imread(
            str(paths[index + 1])
        )

        assert confirm_image is not None

        second_dealer = detect_native_dealer(
            confirm_image
        )

        first_seat = first_dealer.get(
            "dealer_button_seat"
        )

        second_seat = second_dealer.get(
            "dealer_button_seat"
        )

        if not (
            first_seat
            and first_seat == second_seat
            and first_dealer.get("confidence", 0) >= 0.80
            and second_dealer.get("confidence", 0) >= 0.80
        ):
            raise RuntimeError(
                "physical dealer confirmation failed"
            )


        # Read starting stacks from the preserved acquisition frame.
        acquisition_rows = bootstrap_local_stacks(
            canonical_image=image,
            frozen_participants=frozen_participants,
            geometry=GEOMETRY,
            crop_geometry_region=crop_geometry_region,
            stack_reader=read_stack_native_fast,
        )

        acquisition_authority = {
            str(row["seat"]): {
                "stack_bb": float(row["stack_bb"])
            }
            for row in acquisition_rows
            if (
                row.get("seat")
                and row.get("stack_bb") is not None
            )
        }

        print(
            "[PIXEL_ACQUISITION_STACKS]",
            acquisition_authority,
            flush=True,
        )

        snapshot_context = nullcontext()

        if identity_fixture is not None:
            snapshot_result = load_replay_identity_snapshot(
                path,
                identity_fixture,
                frozen_participants,
            )
            snapshot_context = patch(
                "src.v017.run_live_observer.read_table_snapshot_v2",
                return_value=snapshot_result,
            )

        with snapshot_context:
            observer = build_observer_from_frame(
                image,
                path,
                hand_id="pixel-simulation",
                frozen_participants=frozen_participants,
                frozen_stack_authority=acquisition_authority,
                confirmed_dealer_seat=first_seat,
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

    # Finite PNG replay has no future physical frame on which
    # production can naturally collect asynchronous board identity.
    # Drain transport ownership before inspecting final semantic state.
    #
    # This grants no new semantic authority: completed identities are
    # applied through the same production application path, and queued
    # physical boundaries are submitted in their existing order.
    drain_deadline = time.monotonic() + 10.0

    while (
        state.board_identity_reader.future is not None
        or state.pending_board_boundaries
    ):
        completed = (
            state.board_identity_reader.collect_ready()
        )

        if completed is not None:
            finalized = (
                finalize_async_board_identity_result(
                    observer,
                    state,
                    completed,
                    publication_frame="async_drain",
                )
            )

            for reconciled_event in finalized[
                "reconciled_cards"
            ]:
                print(
                    "[PIXEL_ASYNC_CARD_RECONCILED]",
                    f"frame={reconciled_event.get('frame')}",
                    f"seat={reconciled_event.get('seat')}",
                    f"action={reconciled_event.get('semantic_action')}",
                )

            for reconciled_event in finalized[
                "reconciled_quantitative"
            ]:
                print(
                    "[PIXEL_ASYNC_QUANTITATIVE_RECONCILED]",
                    f"frame={reconciled_event.get('frame')}",
                    f"seat={reconciled_event.get('seat')}",
                    f"action={reconciled_event.get('semantic_action')}",
                )

            continue

        if (
            state.board_identity_reader.future is None
            and state.pending_board_boundaries
        ):
            submit_next_pending_board_boundary(
                state
            )
            continue

        if time.monotonic() >= drain_deadline:
            raise RuntimeError(
                "Pixel Lab async board drain timed out"
            )

        time.sleep(0.01)

    print(
        "[PIXEL_ASYNC_DRAIN_COMPLETE]",
        f"street={observer.hand.street}",
        f"board={observer.hand.board}",
        f"actions={len(observer.hand.semantic_actions())}",
    )

    state.board_identity_reader.close()

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
