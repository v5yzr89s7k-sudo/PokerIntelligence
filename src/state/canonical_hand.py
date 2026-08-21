from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
import time


VALID_STREETS = ("PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN", "COMPLETE")

PREFLOP_ACTION_ORDER = (
    "UTG",
    "UTG+1",
    "LJ",
    "HJ",
    "CO",
    "BTN",
    "SB",
    "BB",
)

POSTFLOP_ACTION_ORDER = (
    "SB",
    "BB",
    "UTG",
    "UTG+1",
    "LJ",
    "HJ",
    "CO",
    "BTN",
)


@dataclass
class CanonicalPlayer:
    seat: str
    position: str
    name: str
    starting_stack_bb: Optional[float] = None
    current_stack_bb: Optional[float] = None
    last_confirmed_stack_bb: Optional[float] = None

    # Unresolved perception evidence from the authoritative hand-start
    # snapshot. These values are hypotheses only; they must never be treated
    # as canonical stack state until later evidence uniquely resolves one.
    starting_stack_candidates: List[float] = field(default_factory=list)

    is_hero: bool = False
    folded: bool = False
    all_in: bool = False
    active: bool = True
    committed_by_street: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)



@dataclass
class StreetSummary:
    street: str
    starting_pot_bb: Optional[float] = None
    ending_pot_bb: Optional[float] = None
    started_ts: Optional[float] = None
    ended_ts: Optional[float] = None
    pot_observed: bool = False

    def to_dict(self):
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
        self.dealt_in_seats: List[str] = []
        self.board: List[str] = []
        self.actions: List[CanonicalAction] = []

        self.current_bet_bb = 0.0
        self.pot_bb: Optional[float] = None
        self.expected_pot_bb: Optional[float] = None

        # Extra money independently proven to have existed in the
        # authoritative initial table pot beyond the canonical forced
        # contributions known when that observation was requested.
        #
        # This is evidence-derived and intentionally agnostic about its
        # semantic source (ante, dead money, other forced contribution).
        self.starting_pot_adjustment_bb: float = 0.0
        self.starting_pot_adjustment_established: bool = False

        self.last_aggressor_seat: Optional[str] = None
        self.players_to_act: List[str] = []

        self.street_summaries: Dict[str, StreetSummary] = {}
        self.showdown: List[dict] = []
        self.pots: List[dict] = []
        self.result = ""
        self.closed = False
        self._next_sequence = 1

    def _initialize_players_to_act(self):
        """
        Build the live action queue from authoritative player positions.

        Preflop action begins left of the big blind. Postflop action begins
        with the earliest active position left of the button. Folded and
        all-in players are never included.
        """
        position_order = (
            PREFLOP_ACTION_ORDER
            if self.current_street == "PREFLOP"
            else POSTFLOP_ACTION_ORDER
        )

        seat_by_position = {
            player.position: seat
            for seat, player in self.players.items()
            if player.position not in ("", "unknown")
            and player.active
            and not player.folded
            and not player.all_in
        }

        self.players_to_act = [
            seat_by_position[position]
            for position in position_order
            if position in seat_by_position
        ]

        return list(self.players_to_act)

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
                name=str(item.get("name") or "").strip(),
                starting_stack_bb=float(stack_bb) if stack_bb is not None else None,
                current_stack_bb=float(stack_bb) if stack_bb is not None else None,
                last_confirmed_stack_bb=float(stack_bb) if stack_bb is not None else None,
                starting_stack_candidates=[
                    float(value)
                    for value in (
                        item.get("stack_candidates") or []
                    )
                    if value is not None
                    and float(value) > 0.0
                ],
                is_hero=bool(item.get("is_hero")) or seat == self.hero_seat,
                active=bool(item.get("is_active", True)),
            )

        self._initialize_players_to_act()

        self.street_summaries["PREFLOP"] = StreetSummary(
            street="PREFLOP",
            starting_pot_bb=0.0,
            ending_pot_bb=0.0,
            started_ts=self.started_ts,
        )

        return self

    def update_table_snapshot(
        self,
        players: List[dict],
        hero_position: str,
        positions: Optional[Dict[str, str]] = None,
        dealt_in_seats: Optional[List[str]] = None,
    ):
        positions = positions or {}

        if dealt_in_seats is not None:
            self.dealt_in_seats = list(dealt_in_seats)

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
                current_stack_bb=(
                    existing.current_stack_bb
                    if existing and existing.current_stack_bb is not None
                    else (
                        float(stack_bb)
                        if stack_bb is not None
                        else None
                    )
                ),
                last_confirmed_stack_bb=(
                    existing.last_confirmed_stack_bb
                    if existing and existing.last_confirmed_stack_bb is not None
                    else (
                        float(stack_bb)
                        if stack_bb is not None
                        else None
                    )
                ),
                starting_stack_candidates=(
                    [
                        float(value)
                        for value in (
                            item.get("stack_candidates") or []
                        )
                        if value is not None
                        and float(value) > 0.0
                    ]
                    if "stack_candidates" in item
                    else (
                        list(existing.starting_stack_candidates)
                        if existing
                        else []
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

        # Rebuild the canonical action queue once authoritative positions
        # arrive, but only before the first voluntary preflop action.
        forced_actions = {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }

        prior_voluntary_action = any(
            action.street == "PREFLOP"
            and action.action not in forced_actions
            for action in self.actions
        )

        if (
            self.current_street == "PREFLOP"
            and not prior_voluntary_action
        ):
            self._initialize_players_to_act()

        return self

    def resolve_starting_stack_baseline(
        self,
        seat: str,
        observed_stack_bb: float,
        *,
        tolerance_bb: float = 0.02,
    ) -> Optional[dict]:
        """
        Promote independently observed pre-change stack evidence into the
        canonical starting baseline.

        This is intentionally conservative:
          - the starting baseline must still be unresolved;
          - current/last-confirmed stack state must still be unresolved;
          - the observation must uniquely match exactly one preserved
            starting-stack candidate.

        No action amount or poker-semantic inference is used.
        """
        player = self.players.get(seat)

        if player is None:
            return None

        if (
            player.starting_stack_bb is not None
            or player.current_stack_bb is not None
            or player.last_confirmed_stack_bb is not None
        ):
            return {
                "seat": seat,
                "resolved": False,
                "reason": "canonical_stack_already_initialized",
                "observed_stack_bb": float(observed_stack_bb),
            }

        try:
            observed = float(observed_stack_bb)
        except (TypeError, ValueError):
            return {
                "seat": seat,
                "resolved": False,
                "reason": "invalid_observation",
                "observed_stack_bb": None,
            }

        if observed <= 0.0:
            return {
                "seat": seat,
                "resolved": False,
                "reason": "invalid_observation",
                "observed_stack_bb": observed,
            }

        matches = []

        for candidate in (
            player.starting_stack_candidates or []
        ):
            try:
                candidate_value = float(candidate)
            except (TypeError, ValueError):
                continue

            if candidate_value <= 0.0:
                continue

            if abs(candidate_value - observed) <= tolerance_bb:
                if candidate_value not in matches:
                    matches.append(candidate_value)

        if len(matches) != 1:
            return {
                "seat": seat,
                "resolved": False,
                "reason": (
                    "no_matching_starting_candidate"
                    if not matches
                    else "ambiguous_starting_candidates"
                ),
                "observed_stack_bb": observed,
                "matching_candidates": list(matches),
            }

        resolved = float(matches[0])

        player.starting_stack_bb = resolved
        player.current_stack_bb = resolved
        player.last_confirmed_stack_bb = resolved

        return {
            "seat": seat,
            "resolved": True,
            "reason": "unique_prechange_candidate_match",
            "starting_stack_bb": resolved,
            "current_stack_bb": resolved,
            "last_confirmed_stack_bb": resolved,
            "observed_stack_bb": observed,
        }


    def update_player_stack(
        self,
        seat: str,
        new_stack_bb: float,
    ) -> Optional[dict]:
        player = self.players.get(seat)

        if player is None:
            return None

        new_stack_bb = float(new_stack_bb)
        previous_stack_bb = player.last_confirmed_stack_bb

        if previous_stack_bb is None:
            player.current_stack_bb = new_stack_bb
            player.last_confirmed_stack_bb = new_stack_bb

            return {
                "seat": seat,
                "previous_stack_bb": None,
                "current_stack_bb": new_stack_bb,
                "delta_bb": None,
                "initialized": True,
            }

        delta_bb = round(previous_stack_bb - new_stack_bb, 4)

        player.current_stack_bb = new_stack_bb
        player.last_confirmed_stack_bb = new_stack_bb

        return {
            "seat": seat,
            "previous_stack_bb": previous_stack_bb,
            "current_stack_bb": new_stack_bb,
            "delta_bb": delta_bb,
            "initialized": False,
        }

    def set_board(self, cards: List[str], ts: Optional[float] = None):
        cards = list(cards)

        if len(cards) not in (0, 3, 4, 5):
            raise ValueError(f"Invalid board length: {len(cards)}")

        if len(cards) < len(self.board):
            raise ValueError("Board cannot move backwards")

        previous_street = self.current_street
        transition_ts = ts or time.time()

        if len(cards) == 3:
            next_street = "FLOP"
        elif len(cards) == 4:
            next_street = "TURN"
        elif len(cards) == 5:
            next_street = "RIVER"
        else:
            next_street = "PREFLOP"

        self.board = cards

        if next_street != previous_street:
            previous_summary = self.street_summaries.get(previous_street)

            if previous_summary is not None:
                previous_summary.ended_ts = transition_ts

            if next_street in ("FLOP", "TURN", "RIVER"):
                start_pot = (
                    previous_summary.ending_pot_bb
                    if previous_summary is not None
                    else None
                )

                self.street_summaries[next_street] = StreetSummary(
                    street=next_street,
                    starting_pot_bb=start_pot,

                    # A newly opened street initially contains the same pot
                    # carried forward from the prior street. Canonical actions
                    # or a later observed-pot update may increase or replace it.
                    ending_pot_bb=start_pot,
                    started_ts=transition_ts,
                )

        self.current_street = next_street
        self.current_bet_bb = 0.0
        self.last_aggressor_seat = None

        if self.current_street in ("FLOP", "TURN", "RIVER"):
            self._initialize_players_to_act()
        else:
            self.players_to_act = []

    def ante_committed_bb(
        self,
        seat: str,
        street: Optional[str] = None,
    ) -> float:
        """
        Return dead-money ante committed by one player on one street.

        Antes contribute to the pot, but they do not count toward the live
        betting price used to distinguish calls from raises.
        """
        target_street = (
            street
            or self.current_street
            or "PREFLOP"
        ).upper()

        total = sum(
            float(action.amount_bb or 0.0)
            for action in self.actions
            if action.seat == seat
            and action.street == target_street
            and action.action == "POST_ANTE"
        )

        # Preserve betting-unit precision internally.
        #
        # Tournament antes commonly use fractional BB values such as 0.125.
        # Rounding an ante to two decimals here creates phantom live
        # commitment (0.125 - 0.12 = 0.005), which can turn a legitimate
        # 3.5 BB raise into 3.51 BB and contaminate later call/raise sizing.
        #
        # Human-readable formatting may round separately at the writer layer.
        return round(total, 4)

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
        normalized_action = str(action or "").upper()

        # A folded or inactive player can never take another voluntary action.
        # Forced historical posts remain valid because they are seeded before
        # any fold transition.
        if (
            player is not None
            and (
                player.folded
                or not player.active
            )
            and normalized_action not in {
                "POST_ANTE",
                "POST_SMALL_BLIND",
                "POST_BIG_BLIND",
            }
        ):
            raise ValueError(
                f"player_already_folded_or_inactive: "
                f"seat={seat} action={normalized_action}"
            )

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

                if item.action == "BET":
                    self.current_bet_bb = max(
                        self.current_bet_bb,
                        committed,
                    )
                    self.last_aggressor_seat = seat

            if raise_to_bb is not None:
                # raise_to_bb is the live street commitment, excluding ante
                # dead money. Preserve the ante in total pot accounting while
                # publishing the conventional poker raise-to amount.
                live_raise_to = float(raise_to_bb)
                ante_committed = self.ante_committed_bb(
                    seat,
                    self.current_street,
                )

                committed = (
                    ante_committed
                    + live_raise_to
                )

                self.current_bet_bb = max(
                    self.current_bet_bb,
                    live_raise_to,
                )
                self.last_aggressor_seat = seat

            player.committed_by_street[self.current_street] = committed

            self._recompute_expected_pot_bb()

        return item

    def add_boundary_action(
        self,
        *,
        street: str,
        seat: str,
        action: str,
        amount_bb: Optional[float] = None,
        raise_to_bb: Optional[float] = None,
        all_in: bool = False,
        confidence: Optional[float] = None,
        source: str = "boundary_resolution",
        evidence: Optional[List[str]] = None,
        ts: Optional[float] = None,
    ) -> CanonicalAction:
        """
        Promote a trusted retrospective street-boundary resolution.

        Unlike add_action(), this method may record an action for a street
        that has already ended. It must never mutate the live betting price,
        live aggressor, or current-street action queue.

        This is intentionally narrow infrastructure for independently
        resolved boundary evidence, not a general stale-action escape hatch.
        """
        target_street = str(street or "").upper()
        normalized_action = str(action or "").upper()

        if target_street not in ("PREFLOP", "FLOP", "TURN", "RIVER"):
            raise ValueError(
                f"invalid_boundary_street: {target_street}"
            )

        if normalized_action not in (
            "FOLD",
            "CALL",
            "CHECK",
            "RAISE",
        ):
            raise ValueError(
                f"unsupported_boundary_action: {normalized_action}"
            )

        if normalized_action == "RAISE":
            if raise_to_bb is None:
                raise ValueError(
                    "boundary_raise_requires_explicit_raise_to_bb"
                )

            try:
                raise_to_value = float(raise_to_bb)
            except (TypeError, ValueError):
                raise ValueError(
                    "boundary_raise_requires_explicit_raise_to_bb"
                )

            if raise_to_value <= 0:
                raise ValueError(
                    "boundary_raise_requires_positive_raise_to_bb"
                )

            raise_to_bb = raise_to_value

        player = self.players.get(seat)

        if player is None:
            raise ValueError(
                f"unknown_boundary_seat: {seat}"
            )

        # Boundary promotion must be idempotent. The same asynchronous
        # result may never create duplicate canonical chronology.
        duplicate = next(
            (
                existing
                for existing in self.actions
                if existing.street == target_street
                and existing.seat == seat
                and existing.action == normalized_action
                and existing.source == source
            ),
            None,
        )

        if duplicate is not None:
            return duplicate

        item = CanonicalAction(
            sequence=self._next_sequence,
            ts=ts or time.time(),
            street=target_street,
            seat=seat,
            position=player.position,
            player_name=player.name,
            action=normalized_action,
            amount_bb=amount_bb,
            raise_to_bb=raise_to_bb,
            all_in=all_in,
            confidence=confidence,
            source=source,
            evidence=list(evidence or []),
        )

        self._next_sequence += 1
        self.actions.append(item)

        if normalized_action == "FOLD":
            player.folded = True
            player.active = False

        if all_in:
            player.all_in = True

        committed = float(
            player.committed_by_street.get(
                target_street,
                0.0,
            )
            or 0.0
        )

        if amount_bb is not None:
            committed += float(amount_bb)

        if raise_to_bb is not None:
            ante_committed = self.ante_committed_bb(
                seat,
                target_street,
            )
            committed = (
                ante_committed
                + float(raise_to_bb)
            )

        player.committed_by_street[target_street] = committed

        # Historical commitment affects reconstructed pot accounting, but
        # must not modify current_bet_bb or last_aggressor_seat.
        self._recompute_expected_pot_bb()

        return item


    def _recompute_expected_pot_bb(self):
        """
        Reconstruct the expected pot from canonical commitments.

        The displayed Total value read from ACR remains authoritative in
        pot_bb. This reconstructed value is retained only for validation.
        """
        total = 0.0

        for player in self.players.values():
            total += sum(
                float(v or 0.0)
                for v in player.committed_by_street.values()
            )

        self.expected_pot_bb = round(total, 2)

        # Canonical chip commitments establish a hard lower bound on
        # the pot. An observed table pot may legitimately be ahead of
        # incomplete semantic reconstruction, so observed evidence is
        # preserved. It may not remain below chips that later canonical
        # actions prove have been committed.
        #
        # Effective pot is therefore the maximum of:
        #   - reconstructed canonical commitments,
        #   - accepted observed table pot,
        #   - pot inherited when the current street began.
        #
        # This invariant is independent of player count, positions,
        # action sequence, bet sizing, blinds, antes, and street.
        summary = self.street_summaries.get(
            self.current_street
        )

        expected = float(
            self.expected_pot_bb or 0.0
        )

        reconstructed = round(
            expected
            + float(
                self.starting_pot_adjustment_bb
                or 0.0
            ),
            2,
        )

        observed = (
            float(self.pot_bb)
            if self.pot_bb is not None
            else 0.0
        )

        inherited = 0.0

        if (
            summary is not None
            and summary.starting_pot_bb is not None
        ):
            inherited = float(
                summary.starting_pot_bb
            )

        effective = round(
            max(
                reconstructed,
                observed,
                inherited,
            ),
            2,
        )

        self.pot_bb = effective

        if summary is not None:
            summary.ending_pot_bb = effective


    def establish_starting_pot_adjustment(
        self,
        observed_pot_bb: float,
        forced_pot_baseline_bb: float,
    ) -> float:
        """
        Preserve money independently proven by the authoritative
        initial table-pot observation but absent from the canonical
        forced-contribution ledger frozen for that request.

        The supplied baseline is historical request-time state.
        Current expected_pot_bb is deliberately NOT consulted because
        asynchronous OCR may return after later betting actions.
        """
        observed = round(float(observed_pot_bb), 6)
        baseline = round(float(forced_pot_baseline_bb), 6)

        if observed < 0.0 or baseline < 0.0:
            raise ValueError(
                "Starting pot inputs cannot be negative"
            )

        adjustment = round(
            max(
                0.0,
                observed - baseline,
            ),
            6,
        )

        if not self.starting_pot_adjustment_established:
            self.starting_pot_adjustment_bb = adjustment
            self.starting_pot_adjustment_established = True

        return self.starting_pot_adjustment_bb


    def set_observed_pot(self, pot_bb: float) -> float:
        value = round(float(pot_bb), 2)

        if value < 0.0:
            raise ValueError("Observed pot cannot be negative")

        self.pot_bb = value

        summary = self.street_summaries.get(self.current_street)
        if summary is not None:
            summary.ending_pot_bb = value
            summary.pot_observed = True

        return value

    def add_showdown(
        self,
        seat: str,
        cards: List[str],
        description: str = "",
        ts: Optional[float] = None,
    ):
        player = self.players.get(seat)
        showdown_ts = ts or time.time()

        if self.current_street in ("PREFLOP", "FLOP", "TURN", "RIVER"):
            summary = self.street_summaries.get(self.current_street)

            if summary is not None and summary.ended_ts is None:
                summary.ended_ts = showdown_ts

        self.showdown.append({
            "seat": seat,
            "position": player.position if player else "unknown",
            "player_name": player.name if player else seat,
            "cards": list(cards),
            "description": description,
        })

        self.current_street = "SHOWDOWN"
        self.players_to_act = []

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

        summary = self.street_summaries.get(self.current_street)
        if summary is not None:
            summary.ended_ts = self.ended_ts

        self.current_street = "COMPLETE"
        self.players_to_act = []
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
                name=str(item.get("name") or "").strip(),
                starting_stack_bb=item.get("starting_stack_bb"),
                current_stack_bb=item.get(
                    "current_stack_bb",
                    item.get("starting_stack_bb"),
                ),
                last_confirmed_stack_bb=item.get(
                    "last_confirmed_stack_bb",
                    item.get("starting_stack_bb"),
                ),
                starting_stack_candidates=[
                    float(value)
                    for value in (
                        item.get("starting_stack_candidates")
                        or []
                    )
                    if value is not None
                    and float(value) > 0.0
                ],
                is_hero=bool(item.get("is_hero")),
                folded=bool(item.get("folded")),
                all_in=bool(item.get("all_in")),
                active=bool(item.get("active", True)),
                committed_by_street=dict(
                    item.get("committed_by_street") or {}
                ),
            )

        hand.dealt_in_seats = list(
            data.get("dealt_in_seats") or []
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
        hand.expected_pot_bb = data.get("expected_pot_bb")
        hand.starting_pot_adjustment_bb = float(
            data.get("starting_pot_adjustment_bb")
            or 0.0
        )
        hand.starting_pot_adjustment_established = bool(
            data.get(
                "starting_pot_adjustment_established",
                False,
            )
        )
        hand.last_aggressor_seat = data.get("last_aggressor_seat")
        hand.players_to_act = list(data.get("players_to_act") or [])

        hand.street_summaries = {}

        for street, item in (data.get("street_summaries") or {}).items():
            hand.street_summaries[street] = StreetSummary(
                street=item.get("street") or street,
                starting_pot_bb=(
                    float(item["starting_pot_bb"])
                    if item.get("starting_pot_bb") is not None
                    else None
                ),
                ending_pot_bb=(
                    float(item["ending_pot_bb"])
                    if item.get("ending_pot_bb") is not None
                    else None
                ),
                started_ts=item.get("started_ts"),
                ended_ts=item.get("ended_ts"),
                pot_observed=bool(item.get("pot_observed", False)),
            )

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
            "dealt_in_seats": list(self.dealt_in_seats),
            "board": list(self.board),
            "actions": [action.to_dict() for action in self.actions],
            "current_bet_bb": self.current_bet_bb,
            "pot_bb": self.pot_bb,
            "expected_pot_bb": self.expected_pot_bb,
            "starting_pot_adjustment_bb": (
                self.starting_pot_adjustment_bb
            ),
            "starting_pot_adjustment_established": (
                self.starting_pot_adjustment_established
            ),
            "last_aggressor_seat": self.last_aggressor_seat,
            "players_to_act": list(self.players_to_act),
            "street_summaries": {
                street: summary.to_dict()
                for street, summary in self.street_summaries.items()
            },
            "showdown": list(self.showdown),
            "pots": list(self.pots),
            "result": self.result,
            "closed": self.closed,
        }
