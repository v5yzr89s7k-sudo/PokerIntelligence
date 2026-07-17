from datetime import datetime
from typing import Optional

from src.state.canonical_hand import CanonicalAction, CanonicalHand


def _format_bb(value: Optional[float]) -> str:
    if value is None:
        return ""

    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return f"{text} BB"


def _player_label(action: CanonicalAction) -> str:
    position = action.position if action.position != "unknown" else action.seat

    if action.player_name and action.player_name not in {
        action.seat,
        position,
    }:
        return f"{position} ({action.player_name})"

    return position


def format_action(action: CanonicalAction) -> str:
    player = _player_label(action)
    kind = action.action.upper()

    if kind == "FOLD":
        return f"{player} folds"

    if kind == "CHECK":
        return f"{player} checks"

    if kind == "CALL":
        suffix = " all-in" if action.all_in else ""
        amount = _format_bb(action.amount_bb)
        return f"{player} calls{suffix}" + (f" {amount}" if amount else "")

    if kind == "BET":
        suffix = " all-in" if action.all_in else ""
        amount = _format_bb(action.amount_bb)
        return f"{player} bets{suffix}" + (f" {amount}" if amount else "")

    if kind in {"RAISE", "BET_OR_RAISE"}:
        suffix = " all-in" if action.all_in else ""
        amount = _format_bb(action.raise_to_bb)

        if kind == "BET_OR_RAISE":
            verb = "bets or raises"
        else:
            verb = "raises"

        return f"{player} {verb}{suffix}" + (
            f" to {amount}" if amount else ""
        )

    if kind == "ALL_IN":
        amount = _format_bb(action.raise_to_bb or action.amount_bb)
        return f"{player} goes all-in" + (f" to {amount}" if amount else "")

    return f"{player} {kind.lower().replace('_', ' ')}"


def render_canonical_hand(hand: CanonicalHand) -> str:
    lines = [
        "CURRENT HAND",
        "=" * 72,
    ]

    if hand.started_ts is not None:
        started = datetime.fromtimestamp(hand.started_ts).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        lines.append(f"Started: {started}")

    if hand.hand_id:
        lines.append(f"Hand ID: {hand.hand_id}")

    lines.extend([
        "",
        f"TABLE — {len(hand.players)} players",
        "-" * 72,
    ])

    players = sorted(
        hand.players.values(),
        key=lambda player: (
            player.position == "unknown",
            player.position,
            player.seat,
        ),
    )

    for player in players:
        position = (
            player.position
            if player.position != "unknown"
            else player.seat
        )
        stack = _format_bb(player.starting_stack_bb)
        hero = " [HERO]" if player.is_hero else ""

        lines.append(
            f"{position:<8} {player.name:<22} {stack:>10}{hero}"
        )

    lines.extend([
        "",
        f"Hero Position: {hand.hero_position}",
        f"Hero Cards: {' '.join(hand.hero_cards)}",
    ])

    actions_by_street = {
        street: []
        for street in ("PREFLOP", "FLOP", "TURN", "RIVER")
    }

    for action in hand.actions:
        if action.street in actions_by_street:
            actions_by_street[action.street].append(action)

    lines.extend([
        "",
        "PREFLOP",
        "-" * 72,
    ])

    preflop = actions_by_street["PREFLOP"]
    lines.extend(format_action(item) for item in preflop)
    if not preflop:
        lines.append("")

    if len(hand.board) >= 3:
        lines.extend([
            "",
            f"FLOP: {' '.join(hand.board[:3])}",
            "-" * 72,
        ])

        flop = actions_by_street["FLOP"]
        lines.extend(format_action(item) for item in flop)
        if not flop:
            lines.append("")

    if len(hand.board) >= 4:
        lines.extend([
            "",
            f"TURN: {hand.board[3]}",
            "-" * 72,
        ])

        turn = actions_by_street["TURN"]
        lines.extend(format_action(item) for item in turn)
        if not turn:
            lines.append("")

    if len(hand.board) >= 5:
        lines.extend([
            "",
            f"RIVER: {hand.board[4]}",
            "-" * 72,
        ])

        river = actions_by_street["RIVER"]
        lines.extend(format_action(item) for item in river)
        if not river:
            lines.append("")

    if hand.showdown:
        lines.extend([
            "",
            "SHOWDOWN",
            "-" * 72,
        ])

        for item in hand.showdown:
            position = item.get("position") or item.get("seat")
            name = item.get("player_name") or item.get("seat")
            cards = " ".join(item.get("cards") or [])
            description = item.get("description") or ""

            label = (
                f"{position} ({name})"
                if name not in {position, item.get("seat")}
                else position
            )

            line = f"{label} shows {cards}".rstrip()
            if description:
                line += f" — {description}"

            lines.append(line)

    if hand.pots or hand.result:
        lines.extend([
            "",
            "RESULT",
            "-" * 72,
        ])

        for pot in hand.pots:
            pot_type = str(pot.get("pot_type") or "pot").replace("_", " ").title()
            amount = _format_bb(pot.get("amount_bb"))
            winners = []

            for seat in pot.get("winners") or []:
                player = hand.players.get(seat)
                if player:
                    winners.append(
                        player.position
                        if player.position != "unknown"
                        else player.name
                    )
                else:
                    winners.append(seat)

            line = pot_type
            if amount:
                line += f": {amount}"
            if winners:
                line += f" — Winner: {', '.join(winners)}"

            lines.append(line)

        if hand.result:
            lines.append(hand.result)

    return "\n".join(lines).rstrip() + "\n"
