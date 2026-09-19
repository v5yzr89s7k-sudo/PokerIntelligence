import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


HAND_RE = re.compile(
    r"^Game Hand #(?P<hand_id>\d+)"
    r" - Tournament #(?P<tournament_id>\d+)"
    r" - Holdem \(No Limit\)"
    r" - Level (?P<level>\S+)"
    r" \((?P<sb>[\d.]+)/(?P<bb>[\d.]+)\)"
    r" - (?P<timestamp>.+)$"
)

TABLE_RE = re.compile(
    r"^Table '(?P<table>[^']+)' "
    r"(?P<max_players>\d+)-max "
    r"Seat #(?P<button>\d+) is the button$"
)

SEAT_RE = re.compile(
    r"^Seat (?P<number>\d+): "
    r"(?P<name>.+?) "
    r"\((?P<stack>[\d.]+)\)"
    r"(?P<sitting_out> is sitting out)?$"
)

DEALT_RE = re.compile(
    r"^Dealt to (?P<name>.+?) "
    r"\[(?P<cards>[^\]]+)\]$"
)

ANTE_RE = re.compile(
    r"^(?P<name>.+?) posts ante "
    r"(?P<amount>[\d.]+)$"
)

SB_RE = re.compile(
    r"^(?P<name>.+?) posts the small blind "
    r"(?P<amount>[\d.]+)$"
)

BB_RE = re.compile(
    r"^(?P<name>.+?) posts the big blind "
    r"(?P<amount>[\d.]+)$"
)

FOLD_RE = re.compile(
    r"^(?P<name>.+?) folds$"
)

CHECK_RE = re.compile(
    r"^(?P<name>.+?) checks$"
)

CALL_RE = re.compile(
    r"^(?P<name>.+?) calls "
    r"(?P<amount>[\d.]+)$"
)

BET_RE = re.compile(
    r"^(?P<name>.+?) bets "
    r"(?P<amount>[\d.]+)$"
)

RAISE_RE = re.compile(
    r"^(?P<name>.+?) raises "
    r"(?P<amount>[\d.]+) to "
    r"(?P<to>[\d.]+)$"
)

FLOP_RE = re.compile(
    r"^\*\*\* FLOP \*\*\* "
    r"\[(?P<cards>[^\]]+)\]$"
)

TURN_RE = re.compile(
    r"^\*\*\* TURN \*\*\* "
    r"\[[^\]]+\] "
    r"\[(?P<card>[^\]]+)\]$"
)

RIVER_RE = re.compile(
    r"^\*\*\* RIVER \*\*\* "
    r"\[[^\]]+\] "
    r"\[(?P<card>[^\]]+)\]$"
)

SHOW_RE = re.compile(
    r"^(?P<name>.+?) shows "
    r"\[(?P<cards>[^\]]+)\]"
)

UNCALLED_RE = re.compile(
    r"^Uncalled bet "
    r"\((?P<amount>[\d.]+)\) "
    r"returned to (?P<name>.+)$"
)

TOTAL_POT_RE = re.compile(
    r"^Total pot (?P<amount>[\d.]+)"
)

SUMMARY_WIN_RE = re.compile(
    r"^Seat (?P<seat>\d+): "
    r"(?P<name>.+?) .* won "
    r"(?P<amount>[\d.]+)"
)


@dataclass(frozen=True)
class ACRPlayer:
    seat_number: int
    name: str
    starting_stack: float
    sitting_out: bool


@dataclass(frozen=True)
class ACRAction:
    street: str
    actor: str
    action: str
    amount: Optional[float] = None
    raise_to: Optional[float] = None


@dataclass(frozen=True)
class ACRHand:
    hand_id: str
    tournament_id: str
    level: str
    small_blind: float
    big_blind: float
    timestamp: str
    table: str
    max_players: int
    button_seat: int
    players: Tuple[ACRPlayer, ...]
    hero_name: Optional[str]
    hero_cards: Tuple[str, ...]
    actions: Tuple[ACRAction, ...]
    flop: Tuple[str, ...]
    turn: Optional[str]
    river: Optional[str]
    total_pot: Optional[float]
    winners: Tuple[Tuple[str, float], ...]


def _cards(text):
    return tuple(text.split())


def split_hands(text):
    starts = [
        match.start()
        for match in re.finditer(
            r"(?m)^Game Hand #",
            text,
        )
    ]

    chunks = []

    for index, start in enumerate(starts):
        end = (
            starts[index + 1]
            if index + 1 < len(starts)
            else len(text)
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

    return tuple(chunks)


def parse_hand(text):
    lines = tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip()
    )

    assert lines, "empty hand"

    header = HAND_RE.match(lines[0])
    assert header, lines[0]

    table_match = next(
        (
            TABLE_RE.match(line)
            for line in lines
            if TABLE_RE.match(line)
        ),
        None,
    )
    assert table_match, "missing table line"

    players = []
    actions = []

    hero_name = None
    hero_cards = ()

    street = "PREFLOP"

    flop = ()
    turn = None
    river = None

    total_pot = None
    winners = []

    in_summary = False

    for line in lines[1:]:
        match = SEAT_RE.match(line)

        if match and not in_summary:
            players.append(
                ACRPlayer(
                    seat_number=int(
                        match.group("number")
                    ),
                    name=match.group("name"),
                    starting_stack=float(
                        match.group("stack")
                    ),
                    sitting_out=bool(
                        match.group("sitting_out")
                    ),
                )
            )
            continue

        match = DEALT_RE.match(line)

        if match:
            hero_name = match.group("name")
            hero_cards = _cards(
                match.group("cards")
            )
            continue

        match = ANTE_RE.match(line)

        if match:
            actions.append(
                ACRAction(
                    street="PREFLOP",
                    actor=match.group("name"),
                    action="ANTE",
                    amount=float(
                        match.group("amount")
                    ),
                )
            )
            continue

        match = SB_RE.match(line)

        if match:
            actions.append(
                ACRAction(
                    street="PREFLOP",
                    actor=match.group("name"),
                    action="POST_SMALL_BLIND",
                    amount=float(
                        match.group("amount")
                    ),
                )
            )
            continue

        match = BB_RE.match(line)

        if match:
            actions.append(
                ACRAction(
                    street="PREFLOP",
                    actor=match.group("name"),
                    action="POST_BIG_BLIND",
                    amount=float(
                        match.group("amount")
                    ),
                )
            )
            continue

        match = FLOP_RE.match(line)

        if match:
            street = "FLOP"
            flop = _cards(
                match.group("cards")
            )
            continue

        match = TURN_RE.match(line)

        if match:
            street = "TURN"
            turn = match.group("card")
            continue

        match = RIVER_RE.match(line)

        if match:
            street = "RIVER"
            river = match.group("card")
            continue

        if line == "*** SUMMARY ***":
            in_summary = True
            continue

        if not in_summary:
            match = FOLD_RE.match(line)

            if match:
                actions.append(
                    ACRAction(
                        street,
                        match.group("name"),
                        "FOLD",
                    )
                )
                continue

            match = CHECK_RE.match(line)

            if match:
                actions.append(
                    ACRAction(
                        street,
                        match.group("name"),
                        "CHECK",
                    )
                )
                continue

            match = CALL_RE.match(line)

            if match:
                actions.append(
                    ACRAction(
                        street,
                        match.group("name"),
                        "CALL",
                        amount=float(
                            match.group("amount")
                        ),
                    )
                )
                continue

            match = BET_RE.match(line)

            if match:
                actions.append(
                    ACRAction(
                        street,
                        match.group("name"),
                        "BET",
                        amount=float(
                            match.group("amount")
                        ),
                    )
                )
                continue

            match = RAISE_RE.match(line)

            if match:
                actions.append(
                    ACRAction(
                        street,
                        match.group("name"),
                        "RAISE",
                        amount=float(
                            match.group("amount")
                        ),
                        raise_to=float(
                            match.group("to")
                        ),
                    )
                )
                continue

            match = SHOW_RE.match(line)

            if match:
                actions.append(
                    ACRAction(
                        street,
                        match.group("name"),
                        "SHOW",
                    )
                )
                continue

            match = UNCALLED_RE.match(line)

            if match:
                actions.append(
                    ACRAction(
                        street,
                        match.group("name"),
                        "UNCALLED_RETURN",
                        amount=float(
                            match.group("amount")
                        ),
                    )
                )
                continue

        match = TOTAL_POT_RE.match(line)

        if match:
            total_pot = float(
                match.group("amount")
            )
            continue

        if in_summary:
            match = SUMMARY_WIN_RE.match(line)

            if match:
                winners.append(
                    (
                        match.group("name"),
                        float(
                            match.group("amount")
                        ),
                    )
                )

    return ACRHand(
        hand_id=header.group("hand_id"),
        tournament_id=header.group(
            "tournament_id"
        ),
        level=header.group("level"),
        small_blind=float(
            header.group("sb")
        ),
        big_blind=float(
            header.group("bb")
        ),
        timestamp=header.group(
            "timestamp"
        ),
        table=table_match.group("table"),
        max_players=int(
            table_match.group("max_players")
        ),
        button_seat=int(
            table_match.group("button")
        ),
        players=tuple(players),
        hero_name=hero_name,
        hero_cards=hero_cards,
        actions=tuple(actions),
        flop=flop,
        turn=turn,
        river=river,
        total_pot=total_pot,
        winners=tuple(winners),
    )


def parse_file(path):
    path = Path(path)

    return tuple(
        parse_hand(chunk)
        for chunk in split_hands(
            path.read_text(
                errors="replace"
            )
        )
    )


def parse_corpus(root):
    root = Path(root)

    rows = []

    for path in sorted(
        root.glob("*.txt")
    ):
        for hand in parse_file(path):
            rows.append(
                (path, hand)
            )

    return tuple(rows)
