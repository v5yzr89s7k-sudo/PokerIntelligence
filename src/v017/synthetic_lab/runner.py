from dataclasses import dataclass
from typing import Tuple

import time

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)

from src.v017.run_live_observer import (
    FrameTransactionState,
    process_frame_transaction,
    finalize_async_board_identity_result,
    submit_next_pending_board_boundary,
)

from src.v017.july22_frame_preflop_replay import (
    ACTION_ORDER,
    GEOMETRY,
    PLAYERS,
    TRACKED_STACKS,
    load_board_observations,
)
from src.v017.test_july22_frame_observer_complete_hand import (
    BOUNDARY_STREET,
    OPPONENT_SEATS,
    STREET_ORDER,
)

from src.v017.synthetic_lab.frame_source import (
    RecordedFrameSource,
)
from src.v017.synthetic_lab.progression import (
    ProductSnapshot,
)


@dataclass(frozen=True)
class LabRun:
    scenario: str
    frame_count: int
    publications: Tuple[ProductSnapshot, ...]
    final_actions: tuple
    final_text: str


def build_observer():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
        geometry=GEOMETRY,
        trusted_stacks=dict(TRACKED_STACKS),
        opponent_seats=OPPONENT_SEATS,
        quantitative_seats=[
            "seat_lower_right",
            "hero",
            "seat_lower_left",
        ],
        hero_seat="hero",
        hand_id="synthetic-lab-july22",
    )


def run_july22():
    """
    July22 authentic-pixel laboratory through the same production
    frame transaction used by live ACR.
    """
    source = RecordedFrameSource()
    observer = build_observer()
    state = FrameTransactionState()
    snapshots = []

    # Frame 1 is the acquisition frame: establish physical
    # transition state without treating it as an action frame.
    acquisition_image = source.load(1)
    observer.establish_physical_transition_baseline(
        acquisition_image,
        physical_geometry=GEOMETRY,
        native_frame=acquisition_image,
    )

    for number in range(2, 136):
        before = len(observer.publications)

        path = source.path(number)
        image = source.load(number)

        transaction = process_frame_transaction(
            observer,
            image,
            path,
            number,
            state,
        )

        for publication in observer.publications[
            before:
        ]:
            snapshots.append(
                ProductSnapshot(
                    frame=int(publication["frame"]),
                    street=str(publication["street"]),
                    action_count=int(
                        publication["action_count"]
                    ),
                    next_actor=publication[
                        "next_actor"
                    ],
                    text=publication["text"],
                )
            )

        if transaction.outcome != "CONTINUE":
            break

    # Finite replay must drain production async board ownership
    # before final canonical state is inspected.
    drain_deadline = time.monotonic() + 10.0

    while (
        state.board_identity_reader.future is not None
        or state.pending_board_boundaries
    ):
        completed = (
            state.board_identity_reader.collect_ready()
        )

        if completed is not None:
            before = len(observer.publications)

            finalize_async_board_identity_result(
                observer,
                state,
                completed,
                publication_frame="async_drain",
            )

            for publication in observer.publications[
                before:
            ]:
                snapshots.append(
                    ProductSnapshot(
                        frame=publication["frame"],
                        street=str(publication["street"]),
                        action_count=int(
                            publication["action_count"]
                        ),
                        next_actor=publication[
                            "next_actor"
                        ],
                        text=publication["text"],
                    )
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
                "Synthetic Lab async board drain timed out"
            )

        time.sleep(0.01)

    final_actions = tuple(
        (
            row["street"],
            row["seat"],
            row["action"],
            row["amount_bb"],
            row["raise_to_bb"],
        )
        for row in observer.hand.semantic_actions()
    )

    final_text = (
        observer.publications[-1]["text"]
        if observer.publications
        else ""
    )

    state.board_identity_reader.close()

    return LabRun(
        scenario="july22_baseline",
        frame_count=135,
        publications=tuple(snapshots),
        final_actions=final_actions,
        final_text=final_text,
    )
