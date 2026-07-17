from dataclasses import dataclass, field
from typing import Dict, Set


VOLUNTARY_ACTIONS = {
    "VOLUNTARY_COMMIT",
    "CALL",
    "BET",
    "RAISE",
    "ALL_IN",
}


@dataclass
class StreetCommitmentState:
    street: str
    committed: Set[str] = field(default_factory=set)


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
            street: sorted(state.committed)
            for street, state in self._states.items()
        }
