from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List

from src.observer.observation_types import (
    STACK_CHANGED,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
    POT_CHANGED,
)


UNKNOWN = "UNKNOWN"
BET_OR_RAISE = "BET_OR_RAISE"
CALL_OR_RAISE = "CALL_OR_RAISE"
CALL = "CALL"
FOLD_OR_RESOLVED = "FOLD_OR_RESOLVED"
TABLE_EVENT = "TABLE_EVENT"
POST_SMALL_BLIND = "POST_SMALL_BLIND"
POST_BIG_BLIND = "POST_BIG_BLIND"


@dataclass
class InferredAction:
    episode_id: int
    seat: str
    street: str
    action: str
    confidence: float
    evidence: List[str]
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class ActionInferenceEngine:
    """
    Conservative rule-based conversion of closed ActionEpisodes into
    semantic poker-action candidates.

    This engine intentionally prefers UNKNOWN over unsupported guesses.
    """

    def __init__(self):
        self.processed_episode_ids = set()
        self.actions: List[InferredAction] = []

        # Forced posts may generate multiple visual episodes while their
        # chips remain visible. Publish each forced post only once per hand.
        self.emitted_forced_posts = set()

        # Suppressed episodes remain processed and available in episode
        # diagnostics, but do not contaminate the semantic action stream.
        self.suppressed_episode_ids = set()

    @staticmethod
    def _episode_dict(episode: Any) -> Dict:
        if isinstance(episode, dict):
            return episode

        if hasattr(episode, "to_dict"):
            return episode.to_dict()

        raise TypeError(
            "episode must be an ActionEpisode or dictionary"
        )

    @staticmethod
    def _evidence(episode: Dict) -> List[str]:
        evidence = episode.get("observation_types") or []

        if not evidence:
            evidence = [
                item.get("type")
                for item in episode.get("observations", [])
                if item.get("type")
            ]

        # Preserve first-seen order while removing duplicates.
        return list(dict.fromkeys(evidence))

    def infer_episode(self, episode: Any) -> InferredAction:
        item = self._episode_dict(episode)

        episode_id = int(item.get("episode_id") or 0)
        seat = item.get("seat") or "unknown"
        street = item.get("street") or "unknown"
        evidence = self._evidence(item)
        kinds = set(evidence)
        episode_confidence = float(item.get("confidence") or 0.0)

        table_context = item.get("table_context") or {}
        positions = table_context.get("positions") or {}
        position = positions.get(seat)

        if not position and seat == "hero":
            position = table_context.get("hero_position")

        position = str(position or "unknown").upper()

        prior_committed = set(
            table_context.get(
                "prior_voluntary_commitment_seats"
            )
            or []
        )
        prior_committed.discard(seat)

        prior_occupied = set(
            table_context.get(
                "prior_occupied_bet_regions"
            )
            or []
        )

        # Blind chips do not represent voluntary prior action.
        voluntary_prior_occupied = {
            occupied_seat
            for occupied_seat in prior_occupied
            if str(
                positions.get(occupied_seat)
                or "unknown"
            ).upper() not in {"SB", "BB"}
            and occupied_seat != seat
        }

        action = UNKNOWN
        confidence = min(episode_confidence, 0.45)
        reason = "insufficient evidence"

        if seat == "table" and kinds == {POT_CHANGED}:
            action = TABLE_EVENT
            confidence = min(max(episode_confidence, 0.40), 0.60)
            reason = "table-level pot transition without seat attribution"

        elif (
            STACK_CHANGED in kinds
            and BET_REGION_OCCUPIED in kinds
            and (
                prior_committed
                or voluntary_prior_occupied
            )
        ):
            action = CALL_OR_RAISE
            confidence = min(
                max(episode_confidence, 0.80),
                0.98,
            )
            reason = (
                "seat committed chips while facing prior "
                "non-blind opponent commitment"
            )

        elif STACK_CHANGED in kinds and BET_REGION_OCCUPIED in kinds:
            action = BET_OR_RAISE
            confidence = min(max(episode_confidence, 0.75), 0.98)
            reason = (
                "seat stack changed and a bet region appeared "
                "without confirmed prior voluntary commitment"
            )

        elif (
            street.upper() == "PREFLOP"
            and position == "SB"
            and BET_REGION_OCCUPIED in kinds
            and STACK_CHANGED not in kinds
        ):
            action = POST_SMALL_BLIND
            confidence = min(max(episode_confidence, 0.60), 0.82)
            reason = (
                "preflop SB chip region appeared without "
                "voluntary stack-change evidence"
            )

        elif (
            street.upper() == "PREFLOP"
            and position == "BB"
            and BET_REGION_OCCUPIED in kinds
            and STACK_CHANGED not in kinds
        ):
            action = POST_BIG_BLIND
            confidence = min(max(episode_confidence, 0.65), 0.85)
            reason = (
                "preflop BB chip region appeared without "
                "voluntary stack-change evidence"
            )

        elif (
            STACK_CHANGED in kinds
            and POT_CHANGED in kinds
            and BET_REGION_OCCUPIED not in kinds
        ):
            action = CALL
            confidence = min(max(episode_confidence, 0.65), 0.90)
            reason = "stack and pot changed without a detected new bet region"

        elif (
            BET_REGION_CLEARED in kinds
            and STACK_CHANGED not in kinds
            and BET_REGION_OCCUPIED not in kinds
        ):
            action = FOLD_OR_RESOLVED
            confidence = min(max(episode_confidence, 0.35), 0.60)
            reason = "bet region cleared without chip-commit evidence"

        return InferredAction(
            episode_id=episode_id,
            seat=seat,
            street=street,
            action=action,
            confidence=round(confidence, 2),
            evidence=evidence,
            reason=reason,
        )

    def ingest_closed(self, episodes: Iterable[Any]) -> List[InferredAction]:
        new_actions = []

        for episode in episodes:
            item = self._episode_dict(episode)
            episode_id = int(item.get("episode_id") or 0)

            if episode_id <= 0:
                continue

            if episode_id in self.processed_episode_ids:
                continue

            if not item.get("closed", True):
                continue

            action = self.infer_episode(item)

            # Every closed episode is processed exactly once, including
            # episodes deliberately suppressed below.
            self.processed_episode_ids.add(episode_id)

            evidence = set(action.evidence)

            # A lone bet-region appearance proves only that something became
            # visible in the region. Without stack/pot evidence or blind
            # context, it is not a publishable poker action.
            weak_unknown = (
                action.action == UNKNOWN
                and evidence == {BET_REGION_OCCUPIED}
            )

            if weak_unknown:
                self.suppressed_episode_ids.add(
                    episode_id
                )
                continue

            if action.action in {
                POST_SMALL_BLIND,
                POST_BIG_BLIND,
            }:
                context = (
                    item.get("table_context")
                    or {}
                )
                hand_key = context.get(
                    "hand_started_at"
                )

                forced_post_key = (
                    hand_key,
                    action.seat,
                    action.action,
                )

                if (
                    forced_post_key
                    in self.emitted_forced_posts
                ):
                    self.suppressed_episode_ids.add(
                        episode_id
                    )
                    continue

                self.emitted_forced_posts.add(
                    forced_post_key
                )

            self.actions.append(action)
            new_actions.append(action)

        return new_actions

    def to_dict(self) -> dict:
        return {
            "count": len(self.actions),
            "suppressed_count": len(
                self.suppressed_episode_ids
            ),
            "suppressed_episode_ids": sorted(
                self.suppressed_episode_ids
            ),
            "actions": [
                action.to_dict()
                for action in self.actions
            ],
        }
