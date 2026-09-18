from dataclasses import dataclass
from typing import Tuple

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
from src.v017.quantitative_transaction import (
    process_quantitative_frame,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
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
    Controlled visual laboratory baseline.

    Inputs visible to observer:
        authentic ACR pixels
        initial table facts

    Ground-truth actions are never supplied to the observer.
    """
    source = RecordedFrameSource()
    observer = build_observer()
    boards = load_board_observations()
    settlement_gate = StackSettlementGate()

    snapshots = []

    for number in range(1, 136):
        before = len(observer.publications)

        result = observer.process_frame(
            source.load(number),
            frame_id=number,
        )

        quantitative_result = (
            process_quantitative_frame(
                observer,
                settlement_gate,
                result.events,
            )
        )

        for event in result.events:
            typ = event["type"]

            if typ in {
                "OPPONENT_CARDS_DISAPPEARED",
                "HERO_CARDS_DISAPPEARED_PHYSICAL",
            }:
                observer.admit_card_disappearance(
                    event["seat"],
                    frame_id=number,
                    physical_type=typ,
                )

            elif (
                typ
                == "STACK_QUANTITATIVE_OBSERVATION"
            ):
                # Quantitative authority is processed once per
                # complete physical frame above through the same
                # transaction used by production.
                continue

            elif typ in BOUNDARY_STREET:
                street = BOUNDARY_STREET[typ]
                card_observation = boards[number]

                if (
                    street == "FLOP"
                    and card_observation["hero_cards"]
                ):
                    observer.hand.observe_hero_cards(
                        list(
                            card_observation[
                                "hero_cards"
                            ]
                        )
                    )

                observer.admit_street_boundary(
                    event,
                    action_order=STREET_ORDER[
                        street
                    ],
                    board=list(
                        card_observation["board"]
                    ),
                    complete_pending=(
                        street == "RIVER"
                    ),
                )

        for publication in observer.publications[
            before:
        ]:
            snapshots.append(
                ProductSnapshot(
                    frame=int(
                        publication["frame"]
                    ),
                    street=str(
                        publication["street"]
                    ),
                    action_count=int(
                        publication[
                            "action_count"
                        ]
                    ),
                    next_actor=publication[
                        "next_actor"
                    ],
                    text=publication["text"],
                )
            )

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

    return LabRun(
        scenario="july22_baseline",
        frame_count=135,
        publications=tuple(snapshots),
        final_actions=final_actions,
        final_text=final_text,
    )
