from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional


VOLUNTARY_ACTIONS = {
    "VOLUNTARY_COMMIT",
    "BET_OR_RAISE",
    "CALL_OR_RAISE",
    "CALL",
    "BET",
    "RAISE",
    "ALL_IN",
}


@dataclass
class StreetCommitmentState:
    """
    Canonical betting state for a single street.

    This is intentionally infrastructure only. Runtime behavior will be
    introduced incrementally in later commits.
    """

    street: str

    committed: Set[str] = field(default_factory=set)

    # Immutable action order established at the start of this street.
    street_order: List[str] = field(default_factory=list)

    # Mutable traversal queue synchronized from CanonicalHand.
    pending_to_act: List[str] = field(default_factory=list)

    # Players who still owe a response to the current resolved aggression.
    needs_response_from: List[str] = field(default_factory=list)

    acted: Set[str] = field(default_factory=set)

    last_aggressor: Optional[str] = None

    current_price: float = 0.0

    betting_open: bool = False


class StreetCommitmentTracker:
    """
    Tracks which players have voluntarily committed chips on the
    current betting street.

    Forced blinds are intentionally ignored.
    """

    def __init__(self):
        self._states: Dict[str, StreetCommitmentState] = {}

    def reset_street(self, street: str):
        street = (street or "UNKNOWN").upper()
        self._states[street] = StreetCommitmentState(
            street=street
        )

    def _state(self, street: str):
        street = (street or "UNKNOWN").upper()

        if street not in self._states:
            self.reset_street(street)

        return self._states[street]

    def record_commitment(self, street, seat):
        """
        Record objective chip-commitment evidence even when the exact
        semantic action—call versus raise—has not yet been resolved.
        """
        street = (street or "UNKNOWN").upper()
        seat = seat or ""

        if not seat:
            return False

        self._state(street).committed.add(seat)
        return True

    def ingest(self, canonical_action):
        """
        canonical_action may be CanonicalAction or dict.
        """

        if hasattr(canonical_action, "to_dict"):
            item = canonical_action.to_dict()
        else:
            item = dict(canonical_action)

        street = (item.get("street") or "UNKNOWN").upper()
        seat = item.get("seat") or ""

        action = (item.get("action") or "").upper()

        if action not in VOLUNTARY_ACTIONS:
            return False

        return self.record_commitment(
            street,
            seat,
        )


    def initialize_street_order(self, street, order):
        """
        Capture the authoritative action order once for this street.

        Later queue consumption must not mutate this immutable reference.
        Repeated initialization is intentionally ignored unless the stored
        order is still empty.
        """
        state = self._state(street)

        if not state.street_order:
            state.street_order = list(order or [])

        return list(state.street_order)

    def sync_queue(self, street, pending):
        state = self._state(street)
        state.pending_to_act = list(pending or [])

    def open_response_queue(
        self,
        street,
        aggressor,
        eligible_seats,
    ):
        print("\n" + "=" * 60)
        print("[OPEN_RESPONSE_QUEUE]")
        print(f"street     : {street}")
        print(f"aggressor  : {aggressor}")
        print(f"eligible   : {list(eligible_seats or [])}")
        """
        Rebuild response obligations after a resolved BET or RAISE.

        Ordering begins immediately after the aggressor in immutable
        street_order and wraps around. The aggressor never owes a response
        to their own action.
        """
        state = self._state(street)
        order = list(state.street_order)
        eligible = set(eligible_seats or [])

        if aggressor not in order:
            state.needs_response_from = []
            return []

        index = order.index(aggressor)

        cyclic_after_aggressor = (
            order[index + 1:]
            + order[:index]
        )

        print(f"street_order : {order}")
        print(f"cyclic_order : {cyclic_after_aggressor}")

        state.needs_response_from = [
            seat
            for seat in cyclic_after_aggressor
            if seat in eligible
            and seat != aggressor
        ]

        print(
            f"response_queue : {state.needs_response_from}"
        )
        print("=" * 60)

        return list(state.needs_response_from)

    def record_response(self, street, seat):
        """
        Mark one player as having responded to the current aggression.
        """
        state = self._state(street)

        state.needs_response_from = [
            pending_seat
            for pending_seat in state.needs_response_from
            if pending_seat != seat
        ]

        return list(state.needs_response_from)

    def record_action(
        self,
        street,
        seat,
        *,
        current_price=None,
        last_aggressor=None,
        betting_open=None,
    ):
        state = self._state(street)

        if seat:
            state.acted.add(seat)

        if current_price is not None:
            state.current_price = float(current_price)

        if last_aggressor is not None:
            state.last_aggressor = last_aggressor

        if betting_open is not None:
            state.betting_open = bool(betting_open)

    def players_owing_action(self, street):
        """
        Return the authoritative outstanding action obligations.

        When resolved aggression is open, the response queue is authoritative.
        Otherwise, the canonical street traversal queue is authoritative.
        """
        state = self._state(street)

        if state.betting_open:
            return list(state.needs_response_from)

        return list(state.pending_to_act)

    def is_round_complete(self, street):
        """
        Determine whether the current betting round has completed.

        Completion requires an initialized street order. An unopened round
        completes only when the canonical traversal queue is empty. A round
        containing resolved aggression completes only when every eligible
        player has responded to that aggression.
        """
        state = self._state(street)

        if not state.street_order:
            return False

        return not self.players_owing_action(street)

    def round_status(self, street):
        """
        Return a structured explanation of the current betting-round state.
        """
        state = self._state(street)
        owing = self.players_owing_action(street)
        complete = self.is_round_complete(street)

        if not state.street_order:
            reason = "street action order is not initialized"
        elif owing:
            noun = "player" if len(owing) == 1 else "players"

            if state.betting_open:
                reason = (
                    f"{len(owing)} {noun} still owe a response "
                    "to the current aggression"
                )
            else:
                reason = (
                    f"{len(owing)} {noun} remain in the "
                    "street action queue"
                )
        elif state.betting_open:
            reason = "all required responses to aggression are complete"
        else:
            reason = "street action queue is complete"

        return {
            "street": state.street,
            "complete": complete,
            "reason": reason,
            "betting_open": state.betting_open,
            "current_price": state.current_price,
            "last_aggressor": state.last_aggressor,
            "players_owing_action": owing,
            "pending_to_act": list(state.pending_to_act),
            "needs_response_from": list(
                state.needs_response_from
            ),
            "acted": sorted(state.acted),
        }

    def has_player_committed(self, street, seat):
        return (
            seat
            in self._state(street).committed
        )

    def has_prior_commitment(
        self,
        street,
        excluding_seat=None,
    ):
        committed = set(
            self._state(street).committed
        )

        if excluding_seat:
            committed.discard(excluding_seat)

        return bool(committed)

    def committed_players(self, street):
        return sorted(
            self._state(street).committed
        )

    def to_dict(self):
        return {
            street: {
                "committed": sorted(state.committed),
                "street_order": list(state.street_order),
                "pending_to_act": list(state.pending_to_act),
                "needs_response_from": list(
                    state.needs_response_from
                ),
                "acted": sorted(state.acted),
                "last_aggressor": state.last_aggressor,
                "current_price": state.current_price,
                "betting_open": state.betting_open,
                "round_complete": self.is_round_complete(street),
                "players_owing_action": self.players_owing_action(
                    street
                ),
                "round_status": self.round_status(street),
            }
            for street, state in self._states.items()
        }
