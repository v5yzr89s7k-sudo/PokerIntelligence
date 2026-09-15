"""
V0.17 read-only presentation projection.

HandEngine remains the sole semantic authority.

This module may:
    read authoritative HandEngine state
    format authoritative HandEngine state

This module must never:
    infer poker actions
    alter chronology
    alter folded state
    alter commitments
    alter betting price
    alter pending_to_act
"""


def _format_bb(value):
    value = float(value)
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text} BB"


def _player_label(action):
    position = action["position"]
    name = action["name"]

    if name and name not in {
        action["seat"],
        position,
    }:
        return f"{position} ({name})"

    return position


def format_action(action):
    """
    Pure presentation of an already-authoritative semantic action.

    No semantic classification is permitted here.
    """
    label = _player_label(action)
    kind = action["action"]

    if kind == "POST_SMALL_BLIND":
        return (
            f"{label} posts small blind "
            f"{_format_bb(action['amount_bb'])}"
        )

    if kind == "POST_BIG_BLIND":
        return (
            f"{label} posts big blind "
            f"{_format_bb(action['amount_bb'])}"
        )

    if kind == "FOLD":
        return f"{label} folds"

    if kind == "CHECK":
        return f"{label} checks"

    if kind == "CALL":
        return (
            f"{label} calls "
            f"{_format_bb(action['amount_bb'])}"
        )

    if kind == "BET":
        return (
            f"{label} bets "
            f"{_format_bb(action['amount_bb'])}"
        )

    if kind == "RAISE":
        return (
            f"{label} raises to "
            f"{_format_bb(action['raise_to_bb'])}"
        )

    raise ValueError(
        "unsupported authoritative action: "
        f"{kind}"
    )


def project_hand(hand):
    """
    Return a presentation-only dictionary.

    Every value is copied from HandEngine.
    """
    players = []

    for player in hand.players.values():
        players.append(
            {
                "seat": player.seat,
                "position": player.position,
                "name": player.name,
                "starting_stack_bb": (
                    player.starting_stack_bb
                ),
                "dealt_in": player.dealt_in,
                "folded": player.folded,
            }
        )

    actions = hand.semantic_actions()

    return {
        "street": hand.street,
        "next_actor": hand.next_actor,
        "hero_cards": list(
            hand.hero_cards
        ),
        "board": list(
            hand.board
        ),
        "players": players,
        "actions": actions,
        "formatted_actions": [
            format_action(action)
            for action in actions
        ],
    }
