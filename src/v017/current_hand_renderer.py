"""
V0.17 current_hand.txt renderer.

STRICT RULE:
    HandEngine is the sole semantic authority.

This module formats state only.
It must never infer, classify, reconcile, reorder, or mutate poker state.
"""

from pathlib import Path

from src.v017.hand_projection import (
    format_action,
)


LINE = "=" * 72
SUBLINE = "-" * 72

POSITION_ORDER = {
    "BB": 0,
    "BTN": 1,
    "CO": 2,
    "HJ": 3,
    "LJ": 4,
    "UTG": 5,
    "SB": 6,
}


def _bb(value):
    value = float(value)
    return (
        f"{value:.2f}"
        .rstrip("0")
        .rstrip(".")
        + " BB"
    )


def _actions_for_street(
    hand,
    street,
):
    return [
        action
        for action in hand.semantic_actions()
        if action["street"] == street
    ]


def _hero_player(hand):
    heroes = [
        player
        for player in hand.players.values()
        if player.seat == "hero"
    ]

    if len(heroes) != 1:
        raise ValueError(
            "HandEngine must contain exactly one hero seat"
        )

    return heroes[0]


def _street_header(
    street,
    board,
):
    if street == "PREFLOP":
        return "PREFLOP"

    if street == "FLOP":
        if len(board) < 3:
            raise ValueError(
                "cannot render FLOP without three board cards"
            )
        return (
            "FLOP: "
            + " ".join(board[:3])
        )

    if street == "TURN":
        if len(board) < 4:
            raise ValueError(
                "cannot render TURN without four board cards"
            )
        return (
            "TURN: "
            + board[3]
        )

    if street == "RIVER":
        if len(board) < 5:
            raise ValueError(
                "cannot render RIVER without five board cards"
            )
        return (
            "RIVER: "
            + board[4]
        )

    raise ValueError(
        f"unsupported street: {street}"
    )


def render_current_hand(
    hand,
    *,
    started=None,
    hand_id=None,
):
    """
    Pure rendering function.

    started and hand_id are presentation metadata supplied by the
    caller. They are deliberately not synthesized here.
    """
    hero = _hero_player(hand)

    lines = [
        "CURRENT HAND",
        LINE,
    ]

    if started is not None:
        lines.append(
            f"Started: {started}"
        )

    if hand_id is not None:
        lines.append(
            f"Hand ID: {hand_id}"
        )

    if (
        started is not None
        or hand_id is not None
    ):
        lines.append("")

    players = list(
        hand.players.values()
    )

    players.sort(
        key=lambda player: (
            POSITION_ORDER.get(
                player.position,
                999,
            ),
            player.position,
            player.seat,
        )
    )

    dealt_count = sum(
        1
        for player in players
        if player.dealt_in
    )

    lines.extend(
        [
            f"TABLE — {len(players)} players seated",
            f"HAND — {dealt_count} players dealt",
            SUBLINE,
        ]
    )

    for player in players:
        markers = []

        if player.seat == "hero":
            markers.append("HERO")

        if not player.dealt_in:
            markers.append("NOT DEALT")

        marker = (
            " [" + ", ".join(markers) + "]"
            if markers
            else ""
        )

        lines.append(
            f"{player.position:<8} "
            f"{player.name:<24} "
            f"{_bb(player.starting_stack_bb):>10}"
            f"{marker}"
        )

    lines.extend(
        [
            "",
            f"Hero Position: {hero.position}",
            (
                "Hero Cards: "
                + (
                    " ".join(hand.hero_cards)
                    if hand.hero_cards
                    else "unknown"
                )
            ),
            "",
        ]
    )

    actions = hand.semantic_actions()

    for street in (
        "PREFLOP",
        "FLOP",
        "TURN",
        "RIVER",
    ):
        street_actions = [
            action
            for action in actions
            if action["street"] == street
        ]

        # Do not render streets that have not occurred.
        if (
            street != "PREFLOP"
            and not street_actions
        ):
            continue

        lines.append(
            _street_header(
                street,
                hand.board,
            )
        )
        lines.append(SUBLINE)

        for action in street_actions:
            lines.append(
                format_action(action)
            )

        lines.append("")

    lines.extend(
        [
            "STATUS",
            SUBLINE,
        ]
    )

    if hand.next_actor is None:
        lines.append(
            "Betting round complete"
        )
    else:
        player = hand.players[
            hand.next_actor
        ]

        lines.append(
            "Next Actor: "
            f"{player.position} "
            f"({player.name})"
        )

    return "\n".join(lines).rstrip() + "\n"


def write_current_hand(
    hand,
    path,
    *,
    started=None,
    hand_id=None,
):
    """
    Write a projection atomically.

    Rendering occurs completely before the destination is replaced.
    """
    path = Path(path)

    text = render_current_hand(
        hand,
        started=started,
        hand_id=hand_id,
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    temporary.write_text(text)

    temporary.replace(path)

    return text
