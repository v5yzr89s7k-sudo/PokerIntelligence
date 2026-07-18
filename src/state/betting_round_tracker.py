from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from src.observer.action_inference_engine import (
    UNKNOWN,
    BET_OR_RAISE,
    CALL_OR_RAISE,
    CALL,
    FOLD_OR_RESOLVED,
    TABLE_EVENT,
    POST_SMALL_BLIND,
    POST_BIG_BLIND,
)
from src.state.canonical_hand import CanonicalAction, CanonicalHand
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)


BET = "BET"
RAISE = "RAISE"

# Objective chip-commitment event used until sizing resolves the exact
# semantic action as CALL, BET, or RAISE.
VOLUNTARY_COMMIT = "VOLUNTARY_COMMIT"

# Forced posts are canonical poker events, not voluntary bets.
CANONICAL_POST_SMALL_BLIND = "POST_SMALL_BLIND"
CANONICAL_POST_BIG_BLIND = "POST_BIG_BLIND"


@dataclass
class BettingRoundDecision:
    episode_id: int
    street: str
    seat: str
    inferred_action: str
    canonical_action: Optional[str]
    accepted: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class BettingRoundTracker:
    """
    Converts inferred perception actions into ordered CanonicalHand actions.

    This first phase:
    - distinguishes BET from RAISE
    - preserves CALL
    - preserves ambiguous evidence as UNKNOWN
    - rejects stale-street and table-level events
    - processes each episode only once
    """

    def __init__(
        self,
        hand: CanonicalHand,
        commitment_tracker=None,
    ):
        if not isinstance(hand, CanonicalHand):
            raise TypeError("hand must be a CanonicalHand")

        self.hand = hand
        self.commitment_tracker = (
            commitment_tracker
            or StreetCommitmentTracker()
        )
        self.street = hand.current_street
        self.has_open_bet = bool(
            hand.last_aggressor_seat
            or float(hand.current_bet_bb or 0.0) > 0.0
        )
        self.last_aggressor_seat = hand.last_aggressor_seat
        self.processed_episode_ids = set()
        self.decisions: List[BettingRoundDecision] = []

    @staticmethod
    def _action_dict(action: Any) -> Dict:
        if isinstance(action, dict):
            return action

        if hasattr(action, "to_dict"):
            return action.to_dict()

        raise TypeError(
            "inferred action must be an InferredAction or dictionary"
        )

    def _sync_street(self):
        current = self.hand.current_street

        if current == self.street:
            return

        self.street = current
        self.has_open_bet = False
        self.last_aggressor_seat = None

        self.hand.current_bet_bb = 0.0
        self.hand.last_aggressor_seat = None
        self.hand.players_to_act = []
        self.commitment_tracker.reset_street(
            self.street
        )

    def _record_decision(
        self,
        episode_id: int,
        street: str,
        seat: str,
        inferred_action: str,
        canonical_action: Optional[str],
        accepted: bool,
        reason: str,
    ):
        decision = BettingRoundDecision(
            episode_id=episode_id,
            street=street,
            seat=seat,
            inferred_action=inferred_action,
            canonical_action=canonical_action,
            accepted=accepted,
            reason=reason,
        )
        self.decisions.append(decision)
        return decision

    def ingest(self, inferred_action: Any) -> Optional[CanonicalAction]:
        self._sync_street()
        item = self._action_dict(inferred_action)

        episode_id = int(item.get("episode_id") or 0)
        seat = item.get("seat") or "unknown"
        action = (item.get("action") or UNKNOWN).upper()
        action_street = (
            item.get("street")
            or self.hand.current_street
            or "unknown"
        ).upper()

        if episode_id <= 0:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "missing or invalid episode id",
            )
            return None

        if episode_id in self.processed_episode_ids:
            return None

        self.processed_episode_ids.add(episode_id)

        if action_street != self.hand.current_street:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "action street does not match canonical hand street",
            )
            return None

        if seat in ("", "unknown", "table"):
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "action has no attributable player seat",
            )
            return None

        if action == POST_SMALL_BLIND:
            if action_street != "PREFLOP":
                self._record_decision(
                    episode_id,
                    action_street,
                    seat,
                    action,
                    None,
                    False,
                    "small blind post is only valid preflop",
                )
                return None

            canonical_action = CANONICAL_POST_SMALL_BLIND
            reason = "forced small blind preserved as canonical event"

        elif action == POST_BIG_BLIND:
            if action_street != "PREFLOP":
                self._record_decision(
                    episode_id,
                    action_street,
                    seat,
                    action,
                    None,
                    False,
                    "big blind post is only valid preflop",
                )
                return None

            canonical_action = CANONICAL_POST_BIG_BLIND
            reason = "forced big blind preserved as canonical event"

        elif action in {
            BET_OR_RAISE,
            CALL_OR_RAISE,
        }:
            # Preserve the richest honest semantic available instead of
            # collapsing both candidates into VOLUNTARY_COMMIT.
            canonical_action = action

            if action == CALL_OR_RAISE:
                reason = (
                    "call versus raise remains unresolved; "
                    "preserving inferred semantic"
                )
            else:
                reason = (
                    "bet versus raise remains unresolved; "
                    "preserving inferred semantic"
                )

        elif action == CALL:
            canonical_action = CALL
            reason = "call inference preserved"

        elif action == FOLD_OR_RESOLVED:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "fold versus visual resolution remains ambiguous",
            )
            return None

        elif action == TABLE_EVENT:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "table event is not a player action",
            )
            return None

        elif action == UNKNOWN:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "insufficient evidence; not added to canonical hand",
            )
            return None

        else:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                f"unsupported inferred action: {action}",
            )
            return None

        measurements = item.get("measurements") or {}
        stack_change = measurements.get("stack_change") or {}

        delta_bb = stack_change.get("delta_bb")
        amount_bb = None
        raise_to_bb = None

        if delta_bb is not None:
            try:
                delta_bb = round(float(delta_bb), 2)
            except (TypeError, ValueError):
                delta_bb = None

        if delta_bb is not None and delta_bb > 0:
            player = self.hand.players.get(seat)
            prior_committed = 0.0

            if player is not None:
                prior_committed = float(
                    player.committed_by_street.get(
                        self.hand.current_street,
                        0.0,
                    )
                    or 0.0
                )

            if canonical_action in {
                BET_OR_RAISE,
                RAISE,
            }:
                raise_to_bb = round(prior_committed + delta_bb, 2)

            elif canonical_action in {
                CALL_OR_RAISE,
                CALL,
                BET,
            }:
                amount_bb = delta_bb

        canonical = self.hand.add_action(
            seat=seat,
            action=canonical_action,
            amount_bb=amount_bb,
            raise_to_bb=raise_to_bb,
            confidence=item.get("confidence"),
            source="betting_round_tracker",
            evidence=list(item.get("evidence") or []),
            ts=item.get("ts"),
        )

        self.commitment_tracker.ingest(
            canonical
        )

        # Forced blinds and unresolved voluntary commitments are not
        # sufficient evidence of aggression. Only resolved BET or RAISE
        # events may establish the last aggressor.
        if canonical_action in (BET, RAISE):
            self.has_open_bet = True
            self.last_aggressor_seat = seat
            self.hand.last_aggressor_seat = seat

        self._record_decision(
            episode_id,
            action_street,
            seat,
            action,
            canonical_action,
            True,
            reason,
        )

        return canonical

    def has_prior_commitment(
        self,
        street=None,
        excluding_seat=None,
    ):
        return self.commitment_tracker.has_prior_commitment(
            street or self.hand.current_street,
            excluding_seat=excluding_seat,
        )

    def committed_players(self, street=None):
        return self.commitment_tracker.committed_players(
            street or self.hand.current_street
        )

    def ingest_many(self, inferred_actions: List[Any]) -> List[CanonicalAction]:
        added = []

        for inferred_action in inferred_actions:
            canonical = self.ingest(inferred_action)
            if canonical is not None:
                added.append(canonical)

        return added

    def to_dict(self) -> dict:
        return {
            "street": self.street,
            "has_open_bet": self.has_open_bet,
            "last_aggressor_seat": self.last_aggressor_seat,
            "processed_episode_count": len(self.processed_episode_ids),
            "decision_count": len(self.decisions),
            "decisions": [
                decision.to_dict()
                for decision in self.decisions
            ],
        }
