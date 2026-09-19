from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from src.v017.pixel_lab.acr_hand_parser import (
    ACRHand,
)


@dataclass(frozen=True)
class TruthPlayerState:
    name: str
    seat_number: int
    stack: float
    folded: bool
    sitting_out: bool


@dataclass(frozen=True)
class TruthFrame:
    sequence: int
    street: str
    cause_actor: Optional[str]
    cause_action: str
    board: Tuple[str, ...]
    pot: float
    players: Tuple[TruthPlayerState, ...]


def _snapshot(
    *,
    sequence,
    street,
    cause_actor,
    cause_action,
    board,
    pot,
    players,
    stacks,
    folded,
):
    return TruthFrame(
        sequence=sequence,
        street=street,
        cause_actor=cause_actor,
        cause_action=cause_action,
        board=tuple(board),
        pot=round(pot, 6),
        players=tuple(
            TruthPlayerState(
                name=player.name,
                seat_number=player.seat_number,
                stack=round(
                    stacks[player.name],
                    6,
                ),
                folded=(
                    player.name in folded
                ),
                sitting_out=player.sitting_out,
            )
            for player in players
        ),
    )


def compile_truth_timeline(
    hand: ACRHand,
):
    """
    Private generator truth.

    This module may consume ACR hand history semantics.
    Its output must never cross into observer_input.
    """

    players = hand.players

    stacks: Dict[str, float] = {
        player.name: player.starting_stack
        for player in players
    }

    # Amount committed on the current betting street.
    street_commitment = {
        player.name: 0.0
        for player in players
    }

    folded = set()

    street = "PREFLOP"
    board = []
    pot = 0.0
    sequence = 0
    frames = []

    def emit(actor, action):
        nonlocal sequence

        sequence += 1

        frames.append(
            _snapshot(
                sequence=sequence,
                street=street,
                cause_actor=actor,
                cause_action=action,
                board=board,
                pot=pot,
                players=players,
                stacks=stacks,
                folded=folded,
            )
        )

    # Initial table state before forced contributions.
    emit(
        None,
        "HAND_START",
    )

    action_index = 0

    while action_index < len(hand.actions):
        action = hand.actions[action_index]

        # Street transitions are encoded in each action's street.
        if action.street != street:
            street = action.street

            street_commitment = {
                player.name: 0.0
                for player in players
            }

            if street == "FLOP":
                board = list(hand.flop)
            elif street == "TURN":
                board = list(hand.flop)

                if hand.turn:
                    board.append(hand.turn)
            elif street == "RIVER":
                board = list(hand.flop)

                if hand.turn:
                    board.append(hand.turn)

                if hand.river:
                    board.append(hand.river)

            emit(
                None,
                f"{street}_BOUNDARY",
            )

        actor = action.actor

        assert actor in stacks, (
            hand.hand_id,
            actor,
        )

        if action.action in {
            "ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }:
            amount = float(action.amount)

            stacks[actor] -= amount
            pot += amount

            # Antes are not part of the betting price.
            if action.action != "ANTE":
                street_commitment[
                    actor
                ] += amount

        elif action.action == "FOLD":
            folded.add(actor)

        elif action.action == "CHECK":
            pass

        elif action.action in {
            "CALL",
            "BET",
        }:
            amount = float(action.amount)

            stacks[actor] -= amount
            pot += amount
            street_commitment[
                actor
            ] += amount

        elif action.action == "RAISE":
            # ACR's first numeric field is the amount newly
            # committed by this action. "to" is the resulting
            # street commitment.
            amount = float(action.amount)
            target = float(action.raise_to)

            prior = street_commitment[
                actor
            ]

            assert abs(
                (prior + amount) - target
            ) < 0.011, (
                hand.hand_id,
                actor,
                prior,
                amount,
                target,
            )

            stacks[actor] -= amount
            pot += amount
            street_commitment[
                actor
            ] = target

        elif action.action == "UNCALLED_RETURN":
            amount = float(action.amount)

            stacks[actor] += amount
            pot -= amount

            street_commitment[
                actor
            ] = max(
                0.0,
                street_commitment[actor]
                - amount,
            )

        elif action.action == "SHOW":
            pass

        else:
            raise AssertionError(
                (
                    "unsupported ACR action",
                    hand.hand_id,
                    action,
                )
            )

        assert stacks[actor] >= -0.011, (
            hand.hand_id,
            actor,
            stacks[actor],
            action,
        )

        if abs(stacks[actor]) < 0.011:
            stacks[actor] = 0.0

        emit(
            actor,
            action.action,
        )

        action_index += 1

    # A board can appear without a later action. Ensure the final
    # recorded board is represented in the truth progression.
    target_street = street
    target_board = list(board)

    if hand.river:
        target_street = "RIVER"
        target_board = (
            list(hand.flop)
            + ([hand.turn] if hand.turn else [])
            + [hand.river]
        )
    elif hand.turn:
        target_street = "TURN"
        target_board = (
            list(hand.flop)
            + [hand.turn]
        )
    elif hand.flop:
        target_street = "FLOP"
        target_board = list(hand.flop)

    if (
        target_street != street
        or tuple(target_board) != tuple(board)
    ):
        street = target_street
        board = target_board

        emit(
            None,
            f"{street}_BOUNDARY",
        )

    return tuple(frames)
