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

from src.v017.synthetic_lab.progression import (
    ProductSnapshot,
)
from src.v017.synthetic_lab.scenario_factory import (
    FactoryScenario,
    PhysicalEvidence,
    validate_scenario,
)


@dataclass(frozen=True)
class FactoryRun:
    scenario: str
    publications: Tuple[ProductSnapshot, ...]
    final_actions: tuple
    final_text: str


def _players(scenario):
    return [
        {
            "seat": player.seat,
            "position": player.position,
            "name": player.name,
            "stack_bb": player.stack_bb,
            "is_hero": player.is_hero,
        }
        for player in scenario.players
    ]


def _quantitative_seats(scenario):
    return tuple(
        player.seat
        for player in scenario.players
    )


def _opponent_seats(scenario):
    return tuple(
        player.seat
        for player in scenario.players
        if player.seat != scenario.hero_seat
    )


def build_factory_observer(scenario):
    validate_scenario(scenario)

    players = _players(scenario)

    return FrameHandObserver(
        players=players,
        action_order=list(
            scenario.action_order
        ),
        small_blind_seat=(
            scenario.small_blind_seat
        ),
        big_blind_seat=(
            scenario.big_blind_seat
        ),
        geometry={
            "stack_regions": {},
            "hole_cards": {},
            "hero_cards": {},
            "board": {},
        },
        trusted_stacks={
            player.seat: player.stack_bb
            for player in scenario.players
        },
        opponent_seats=list(
            _opponent_seats(scenario)
        ),
        quantitative_seats=list(
            _quantitative_seats(scenario)
        ),
        hero_seat=scenario.hero_seat,
        hand_id=(
            f"synthetic-{scenario.name}"
        ),
    )


def _stack_event(item):
    assert item.seat is not None
    assert item.prior is not None
    assert item.value is not None

    return {
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": item.seat,
        "frame": item.frame,
        "resolved": True,
        "resolved_value": item.value,
        "prior": item.prior,
        "confidence": item.confidence,
        "votes": item.votes,
        "mode": item.mode,
    }


def _snapshot(publication):
    return ProductSnapshot(
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


def _record_new_publications(
    observer,
    before,
    snapshots,
):
    for publication in observer.publications[
        before:
    ]:
        snapshots.append(
            _snapshot(publication)
        )


def _run_card_disappearance(
    observer,
    item,
):
    assert item.seat is not None

    physical_type = (
        "HERO_CARDS_DISAPPEARED_PHYSICAL"
        if item.seat == observer.hero_seat
        else "OPPONENT_CARDS_DISAPPEARED"
    )

    observer.admit_card_disappearance(
        item.seat,
        frame_id=item.frame,
        physical_type=physical_type,
    )


def _run_stack_frame(
    observer,
    gate,
    items,
):
    events = tuple(
        _stack_event(item)
        for item in items
    )

    # Explicit physical all-in evidence belongs to the same
    # physical frame transaction.
    for item in items:
        if (
            item.type == "STACK"
            and item.all_in_physical
            and item.seat is not None
        ):
            observer.confirmed_bet_regions.add(
                item.seat
            )

    return process_quantitative_frame(
        observer,
        gate,
        events,
    )


def _run_street_boundary(
    observer,
    item,
):
    boundary_contract = {
        "FLOP": (
            "FLOP_BOUNDARY_PHYSICAL",
            3,
        ),
        "TURN": (
            "TURN_BOUNDARY_PHYSICAL",
            4,
        ),
        "RIVER": (
            "RIVER_BOUNDARY_PHYSICAL",
            5,
        ),
    }

    if item.street not in boundary_contract:
        raise ValueError(
            "unsupported factory street boundary: "
            f"{item.street}"
        )

    physical_type, board_count = (
        boundary_contract[item.street]
    )

    board = list(item.board)

    if len(board) != board_count:
        raise ValueError(
            "factory street boundary board length mismatch: "
            f"street={item.street} "
            f"cards={len(board)} "
            f"expected={board_count}"
        )

    action_order = [
        seat
        for seat in observer.hand.action_order
        if (
            seat in observer.hand.players
            and observer.hand.players[seat].dealt_in
            and not observer.hand.players[seat].folded
        )
    ]

    return observer.admit_street_boundary(
        {
            "frame": item.frame,
            "type": physical_type,
            "board_count": board_count,
        },
        action_order=action_order,
        board=board,
        complete_pending=True,
    )


def run_factory_scenario(scenario):
    validate_scenario(scenario)

    observer = build_factory_observer(
        scenario
    )

    gate = StackSettlementGate()
    snapshots = []

    by_frame = {}

    for item in scenario.evidence:
        by_frame.setdefault(
            item.frame,
            [],
        ).append(item)

    for frame in sorted(by_frame):
        items = tuple(by_frame[frame])
        before = len(observer.publications)

        stack_items = tuple(
            item
            for item in items
            if item.type == "STACK"
        )

        if stack_items:
            _run_stack_frame(
                observer,
                gate,
                stack_items,
            )

        for item in items:
            if item.type == "CARD_DISAPPEARANCE":
                _run_card_disappearance(
                    observer,
                    item,
                )

            elif item.type == "STREET_BOUNDARY":
                _run_street_boundary(
                    observer,
                    item,
                )

            elif item.type == "STACK":
                continue

            else:
                raise ValueError(
                    "unsupported factory evidence type: "
                    f"{item.type}"
                )

        _record_new_publications(
            observer,
            before,
            snapshots,
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

    return FactoryRun(
        scenario=scenario.name,
        publications=tuple(snapshots),
        final_actions=final_actions,
        final_text=final_text,
    )
