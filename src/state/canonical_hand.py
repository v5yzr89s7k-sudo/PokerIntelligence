from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
import time


VALID_STREETS = ("PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN", "COMPLETE")


@dataclass
class CanonicalPlayer:
    seat: str
    position: str
    name: str
    starting_stack_bb: Optional[float] = None
    is_hero: bool = False
    folded: bool = False
    all_in: bool = False
    active: bool = True
    committed_by_street: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CanonicalAction:
    sequence: int
    ts: float
    street: str
    seat: str
    position: str
    player_name: str
    action: str
    amount_bb: Optional[float] = None
    raise_to_bb: Optional[float] = None
    all_in: bool = False
    confidence: Optional[float] = None
    source: str = ""
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class CanonicalHand:
    def __init__(self):
        self.reset()

    def reset(self):
        self.hand_id: Optional[str] = None
        self.started_ts: Optional[float] = None
        self.ended_ts: Optional[float] = None
        self.current_street = "PREFLOP"

        self.hero_cards: List[str] = []
        self.hero_seat = "hero"
        self.hero_position = "unknown"

        self.players: Dict[str, CanonicalPlayer] = {}
        self.board: List[str] = []
        self.actions: List[CanonicalAction] = []

        self.current_bet_bb = 0.0
        self.pot_bb: Optional[float] = None
        self.last_aggressor_seat: Optional[str] = None
        self.players_to_act: List[str] = []

        self.showdown: List[dict] = []
        self.pots: List[dict] = []
        self.result = ""
        self.closed = False
        self._next_sequence = 1

    def start_hand(
        self,
        hand_id: str,
        players: List[dict],
        hero_cards: List[str],
        hero_position: str,
        positions: Optional[Dict[str, str]] = None,
        started_ts: Optional[float] = None,
    ):
        self.reset()

        self.hand_id = hand_id
        self.started_ts = started_ts or time.time()
        self.hero_cards = list(hero_cards)
        self.hero_position = hero_position or "unknown"

        positions = positions or {}

        for item in players:
            seat = item.get("seat") or ""
            if not seat:
                continue

            stack_bb = item.get("stack_bb")

            self.players[seat] = CanonicalPlayer(
                seat=seat,
                position=positions.get(seat, "unknown"),
                name=item.get("name") or seat,
                starting_stack_bb=float(stack_bb) if stack_bb is not None else None,
                is_hero=bool(item.get("is_hero")) or seat == self.hero_seat,
                active=bool(item.get("is_active", True)),
            )

        return self

    def update_table_snapshot(
        self,
        players: List[dict],
        hero_position: str,
        positions: Optional[Dict[str, str]] = None,
    ):
        positions = positions or {}

        self.hero_position = hero_position or self.hero_position

        updated = {}

        for item in players:
            seat = item.get("seat") or ""
            if not seat:
                continue

            existing = self.players.get(seat)
            stack_bb = item.get("stack_bb")

            updated[seat] = CanonicalPlayer(
                seat=seat,
                position=positions.get(
                    seat,
                    existing.position if existing else "unknown",
                ),
                name=item.get("name")
                or (existing.name if existing else seat),
                starting_stack_bb=(
                    float(stack_bb)
                    if stack_bb is not None
                    else (
                        existing.starting_stack_bb
                        if existing
                        else None
                    )
                ),
                is_hero=(
                    bool(item.get("is_hero"))
                    or seat == self.hero_seat
                ),
                folded=existing.folded if existing else False,
                all_in=existing.all_in if existing else False,
                active=(
                    existing.active
                    if existing
                    else bool(item.get("is_active", True))
                ),
                committed_by_street=(
                    dict(existing.committed_by_street)
                    if existing
                    else {}
                ),
            )

        self.players = updated

        # Actions may arrive before the asynchronous table snapshot.
        # Refresh their display metadata once authoritative player and
        # position information becomes available.
        for action in self.actions:
            player = self.players.get(action.seat)
            if player is None:
                continue

            action.position = player.position
            action.player_name = player.name

        return self

    def set_board(self, cards: List[str]):
        cards = list(cards)

        if len(cards) not in (0, 3, 4, 5):
            raise ValueError(f"Invalid board length: {len(cards)}")

        if len(cards) < len(self.board):
            raise ValueError("Board cannot move backwards")

        self.board = cards

        if len(cards) == 3:
            self.current_street = "FLOP"
        elif len(cards) == 4:
            self.current_street = "TURN"
        elif len(cards) == 5:
            self.current_street = "RIVER"

        self.current_bet_bb = 0.0
        self.last_aggressor_seat = None

    def add_action(
        self,
        seat: str,
        action: str,
        amount_bb: Optional[float] = None,
        raise_to_bb: Optional[float] = None,
        all_in: bool = False,
        confidence: Optional[float] = None,
        source: str = "",
        evidence: Optional[List[str]] = None,
        ts: Optional[float] = None,
    ) -> CanonicalAction:
        player = self.players.get(seat)

        position = player.position if player else "unknown"
        player_name = player.name if player else seat

        item = CanonicalAction(
            sequence=self._next_sequence,
            ts=ts or time.time(),
            street=self.current_street,
            seat=seat,
            position=position,
            player_name=player_name,
            action=action.upper(),
            amount_bb=amount_bb,
            raise_to_bb=raise_to_bb,
            all_in=all_in,
            confidence=confidence,
            source=source,
            evidence=list(evidence or []),
        )

        self._next_sequence += 1
        self.actions.append(item)

        if player:
            if item.action == "FOLD":
                player.folded = True
                player.active = False

            if all_in:
                player.all_in = True

            committed = player.committed_by_street.get(self.current_street, 0.0)

            if amount_bb is not None:
                committed += float(amount_bb)

            if raise_to_bb is not None:
                committed = float(raise_to_bb)
                self.current_bet_bb = max(self.current_bet_bb, committed)
                self.last_aggressor_seat = seat

            player.committed_by_street[self.current_street] = committed

        return item

    def add_showdown(
        self,
        seat: str,
        cards: List[str],
        description: str = "",
    ):
        player = self.players.get(seat)

        self.showdown.append({
            "seat": seat,
            "position": player.position if player else "unknown",
            "player_name": player.name if player else seat,
            "cards": list(cards),
            "description": description,
        })

        self.current_street = "SHOWDOWN"

    def add_pot_result(
        self,
        pot_type: str,
        amount_bb: Optional[float],
        winners: List[str],
    ):
        self.pots.append({
            "pot_type": pot_type,
            "amount_bb": amount_bb,
            "winners": list(winners),
        })

    def finish(self, result: str = "", ended_ts: Optional[float] = None):
        self.result = result
        self.ended_ts = ended_ts or time.time()
        self.current_street = "COMPLETE"
        self.closed = True

    @classmethod
    def from_dict(cls, data: dict):
        hand = cls()

        hand.hand_id = data.get("hand_id")
        hand.started_ts = data.get("started_ts")
        hand.ended_ts = data.get("ended_ts")
        hand.current_street = data.get("current_street") or "PREFLOP"

        hand.hero_cards = list(data.get("hero_cards") or [])
        hand.hero_seat = data.get("hero_seat") or "hero"
        hand.hero_position = data.get("hero_position") or "unknown"

        hand.players = {}
        players = data.get("players") or {}

        if isinstance(players, list):
            players = {
                item.get("seat"): item
                for item in players
                if item.get("seat")
            }

        for seat, item in players.items():
            hand.players[seat] = CanonicalPlayer(
                seat=item.get("seat") or seat,
                position=item.get("position") or "unknown",
                name=item.get("name") or seat,
                starting_stack_bb=item.get("starting_stack_bb"),
                is_hero=bool(item.get("is_hero")),
                folded=bool(item.get("folded")),
                all_in=bool(item.get("all_in")),
                active=bool(item.get("active", True)),
                committed_by_street=dict(
                    item.get("committed_by_street") or {}
                ),
            )

        hand.board = list(data.get("board") or [])

        hand.actions = [
            CanonicalAction(
                sequence=int(item.get("sequence") or 0),
                ts=float(item.get("ts") or 0.0),
                street=item.get("street") or "PREFLOP",
                seat=item.get("seat") or "",
                position=item.get("position") or "unknown",
                player_name=item.get("player_name") or item.get("seat") or "",
                action=item.get("action") or "UNKNOWN",
                amount_bb=item.get("amount_bb"),
                raise_to_bb=item.get("raise_to_bb"),
                all_in=bool(item.get("all_in")),
                confidence=item.get("confidence"),
                source=item.get("source") or "",
                evidence=list(item.get("evidence") or []),
            )
            for item in data.get("actions") or []
        ]

        hand.current_bet_bb = float(data.get("current_bet_bb") or 0.0)
        hand.pot_bb = data.get("pot_bb")
        hand.last_aggressor_seat = data.get("last_aggressor_seat")
        hand.players_to_act = list(data.get("players_to_act") or [])

        hand.showdown = list(data.get("showdown") or [])
        hand.pots = list(data.get("pots") or [])
        hand.result = data.get("result") or ""
        hand.closed = bool(data.get("closed"))

        hand._next_sequence = (
            max(
                (action.sequence for action in hand.actions),
                default=0,
            )
            + 1
        )

        return hand

    def to_dict(self) -> dict:
        return {
            "hand_id": self.hand_id,
            "started_ts": self.started_ts,
            "ended_ts": self.ended_ts,
            "current_street": self.current_street,
            "hero_cards": list(self.hero_cards),
            "hero_seat": self.hero_seat,
            "hero_position": self.hero_position,
            "players": {
                seat: player.to_dict()
                for seat, player in self.players.items()
            },
            "board": list(self.board),
            "actions": [action.to_dict() for action in self.actions],
            "current_bet_bb": self.current_bet_bb,
            "pot_bb": self.pot_bb,
            "last_aggressor_seat": self.last_aggressor_seat,
            "players_to_act": list(self.players_to_act),
            "showdown": list(self.showdown),
            "pots": list(self.pots),
            "result": self.result,
            "closed": self.closed,
        }
