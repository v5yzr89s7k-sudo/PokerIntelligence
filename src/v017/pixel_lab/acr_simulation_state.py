"""
Private ACR hand-history simulation state.

GENERATOR SIDE ONLY.

Authority:
    ACRHand parsed from an authentic ACR hand history.

This module knows private truth and MUST NEVER be imported by the
production observer or observer_runner.

It produces deterministic poker-table states for the physical renderer.
Only rendered PNG pixels may cross the simulation isolation wall.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class SimPlayerState:
    seat_number: int
    name: str
    stack_chips: float
    stack_bb: float
    folded: bool
    sitting_out: bool


@dataclass(frozen=True)
class SimTableState:
    sequence: int
    phase: str
    cause_actor: Optional[str]
    cause_action: str

    button_seat: int
    small_blind_seat: int
    big_blind_seat: int

    hero_name: str
    hero_cards: Tuple[str, ...]

    board: Tuple[str, ...]

    pot_chips: float
    pot_bb: float

    players: Tuple[SimPlayerState, ...]

    winner: Optional[str] = None
    result_chips: Optional[float] = None


def _round_bb(chips, big_blind):
    return round(
        float(chips) / float(big_blind),
        2,
    )


def _player_by_name(hand):
    return {
        player.name: player
        for player in hand.players
    }


def _blind_actor(hand, action_name):
    matches = [
        action.actor
        for action in hand.actions
        if action.action == action_name
    ]

    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {action_name}: "
            f"{matches}"
        )

    return matches[0]


def _seat_for_name(hand, name):
    player = _player_by_name(hand)[name]
    return int(player.seat_number)


def _snapshot(
    *,
    hand,
    sequence,
    phase,
    cause_actor,
    cause_action,
    stacks,
    folded,
    board,
    pot,
    small_blind_seat,
    big_blind_seat,
    winner=None,
    result_chips=None,
):
    players = tuple(
        SimPlayerState(
            seat_number=int(player.seat_number),
            name=player.name,
            stack_chips=round(
                float(stacks[player.name]),
                6,
            ),
            stack_bb=_round_bb(
                stacks[player.name],
                hand.big_blind,
            ),
            folded=bool(
                folded[player.name]
            ),
            sitting_out=bool(
                player.sitting_out
            ),
        )
        for player in hand.players
    )

    return SimTableState(
        sequence=int(sequence),
        phase=str(phase),
        cause_actor=cause_actor,
        cause_action=str(cause_action),
        button_seat=int(
            hand.button_seat
        ),
        small_blind_seat=int(
            small_blind_seat
        ),
        big_blind_seat=int(
            big_blind_seat
        ),
        hero_name=str(
            hand.hero_name or ""
        ),
        hero_cards=tuple(
            hand.hero_cards
        ),
        board=tuple(board),
        pot_chips=round(
            float(pot),
            6,
        ),
        pot_bb=_round_bb(
            pot,
            hand.big_blind,
        ),
        players=players,
        winner=winner,
        result_chips=(
            None
            if result_chips is None
            else round(
                float(result_chips),
                6,
            )
        ),
    )


def compile_simulation_states(hand):
    """
    Compile one deterministic physical-table state progression.

    The progression contains actual poker events only. It does not add
    arbitrary duplicate frames. Playback dwell belongs to the playback
    harness, not poker truth.

    Pot semantics:
      * forced contributions enter the pot immediately;
      * calls/bets/raises contribute the actual additional chips paid;
      * raises use ACR's `amount` field, which is the incremental amount
        paid on that action;
      * checks/folds contribute zero;
      * returned uncalled bets are not represented by ACRAction today;
      * final result is taken from parsed ACR summary truth.
    """

    if not hand.players:
        raise ValueError(
            "simulation requires players"
        )

    if not hand.hero_name:
        raise ValueError(
            "simulation requires Hero identity"
        )

    if not hand.hero_cards:
        raise ValueError(
            "simulation requires Hero cards"
        )

    big_blind = float(
        hand.big_blind
    )

    if big_blind <= 0:
        raise ValueError(
            f"invalid big blind: {big_blind}"
        )

    players = _player_by_name(hand)

    stacks: Dict[str, float] = {
        player.name:
            float(player.starting_stack)
        for player in hand.players
    }

    folded = {
        player.name: False
        for player in hand.players
    }

    sb_name = _blind_actor(
        hand,
        "POST_SMALL_BLIND",
    )

    bb_name = _blind_actor(
        hand,
        "POST_BIG_BLIND",
    )

    sb_seat = _seat_for_name(
        hand,
        sb_name,
    )

    bb_seat = _seat_for_name(
        hand,
        bb_name,
    )

    states = []
    sequence = 0
    pot = 0.0
    board = ()

    def emit(
        phase,
        actor,
        action,
        *,
        winner=None,
        result_chips=None,
    ):
        nonlocal sequence

        sequence += 1

        states.append(
            _snapshot(
                hand=hand,
                sequence=sequence,
                phase=phase,
                cause_actor=actor,
                cause_action=action,
                stacks=stacks,
                folded=folded,
                board=board,
                pot=pot,
                small_blind_seat=sb_seat,
                big_blind_seat=bb_seat,
                winner=winner,
                result_chips=result_chips,
            )
        )

    # Pure starting table:
    # players, starting stacks, dealer and Hero cards are known to the
    # simulator, but no forced contribution has yet been deducted.
    emit(
        "SETUP",
        None,
        "STARTING_TABLE",
    )

    # ACR histories list each ante individually. Preserve that physical
    # chronology so the simulated stack visibly changes as it would live.
    preflop_actions = [
        action
        for action in hand.actions
        if action.street == "PREFLOP"
    ]

    index = 0

    while (
        index < len(preflop_actions)
        and preflop_actions[index].action
        == "ANTE"
    ):
        action = preflop_actions[index]
        amount = float(
            action.amount or 0.0
        )

        stacks[action.actor] -= amount
        pot += amount

        emit(
            "PREFLOP",
            action.actor,
            "ANTE",
        )

        index += 1

    # Blinds are the next forced contributions.
    while (
        index < len(preflop_actions)
        and preflop_actions[index].action
        in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ):
        action = preflop_actions[index]
        amount = float(
            action.amount or 0.0
        )

        stacks[action.actor] -= amount
        pot += amount

        emit(
            "PREFLOP",
            action.actor,
            action.action,
        )

        index += 1

    # Explicit hole-card/deal boundary before voluntary action.
    emit(
        "PREFLOP",
        hand.hero_name,
        "HOLE_CARDS",
    )

    # Track per-street commitments so raise-to amounts can be validated.
    commitments = {
        name: 0.0
        for name in players
    }

    # Blinds count as preflop commitments.
    for action in preflop_actions:
        if action.action in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }:
            commitments[action.actor] += float(
                action.amount or 0.0
            )

    current_price = max(
        commitments.values()
    )

    def apply_voluntary(action):
        nonlocal pot
        nonlocal current_price

        actor = action.actor

        if actor not in stacks:
            raise ValueError(
                f"unknown actor: {actor}"
            )

        if action.action == "FOLD":
            folded[actor] = True
            return

        if action.action == "CHECK":
            return

        # SHOW is a showdown visibility event, not a betting action.
        # It changes no stack, commitment, current price, or pot.
        # Preserve it in the simulator chronology so the physical
        # renderer can later expose showdown cards, but never give it
        # monetary semantics.
        if action.action == "SHOW":
            return

        if action.action in {
            "CALL",
            "BET",
        }:
            paid = float(
                action.amount or 0.0
            )

            stacks[actor] -= paid
            commitments[actor] += paid
            pot += paid

            current_price = max(
                current_price,
                commitments[actor],
            )
            return

        if action.action == "RAISE":
            paid = float(
                action.amount or 0.0
            )

            stacks[actor] -= paid
            commitments[actor] += paid
            pot += paid

            if action.raise_to is not None:
                current_price = max(
                    current_price,
                    float(action.raise_to),
                )
            else:
                current_price = max(
                    current_price,
                    commitments[actor],
                )
            return

        raise ValueError(
            f"unsupported action: {action}"
        )

    # Remaining preflop voluntary actions.
    for action in preflop_actions[index:]:
        apply_voluntary(action)

        emit(
            "PREFLOP",
            action.actor,
            action.action,
        )

    street_specs = (
        (
            "FLOP",
            tuple(hand.flop),
        ),
        (
            "TURN",
            (
                tuple(hand.flop)
                + (
                    (hand.turn,)
                    if hand.turn
                    else ()
                )
            ),
        ),
        (
            "RIVER",
            (
                tuple(hand.flop)
                + (
                    (hand.turn,)
                    if hand.turn
                    else ()
                )
                + (
                    (hand.river,)
                    if hand.river
                    else ()
                )
            ),
        ),
    )

    for street, street_board in street_specs:
        actions = [
            action
            for action in hand.actions
            if action.street == street
        ]

        if (
            not actions
            and not street_board
        ):
            continue

        board = street_board

        commitments = {
            name: 0.0
            for name in players
        }

        current_price = 0.0

        emit(
            street,
            None,
            f"{street}_BOUNDARY",
        )

        for action in actions:
            apply_voluntary(action)

            emit(
                street,
                action.actor,
                action.action,
            )

    if hand.winners:
        # Current parser records summary winners as (name, amount).
        # Emit each if a split pot ever appears.
        for winner_name, amount in hand.winners:
            emit(
                "RESULT",
                winner_name,
                "WINNER",
                winner=winner_name,
                result_chips=float(amount),
            )
    else:
        emit(
            "RESULT",
            None,
            "HAND_COMPLETE",
        )

    return tuple(states)
