from dataclasses import dataclass
from typing import List


@dataclass
class ActionQualification:
    episode_id: int
    seat: str
    street: str

    # The actual candidate poker action is explicit in the qualification.
    action: str
    confidence: float
    evidence: List[str]

    evidence_mature: bool
    maturity_reason: str

    publish: bool
    qualification_reason: str

    def to_dict(self):
        return {
            "episode_id": self.episode_id,
            "seat": self.seat,
            "street": self.street,
            "action": self.action,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "evidence_mature": self.evidence_mature,
            "maturity_reason": self.maturity_reason,
            "publish": self.publish,
            "qualification_reason": self.qualification_reason,
        }


class ActionQualifier:
    """
    Semantic gate between action inference and canonical publication.

    Phase 1 is pass-through only:
      - every candidate action remains publishable;
      - qualification records the inferred ACTION explicitly;
      - evidence maturity is exposed for diagnostics.

    A later phase may retire immature candidate actions here without
    changing episode scheduling or action inference.
    """

    def __init__(self):
        # Ordered diagnostic history of every candidate ACTION that reached
        # semantic qualification during this observer run.
        self.qualifications = []

    def to_dict(self):
        return {
            "count": len(self.qualifications),
            "published_count": sum(
                1
                for item in self.qualifications
                if item.get("publish")
            ),
            "retired_count": sum(
                1
                for item in self.qualifications
                if not item.get("publish")
            ),
            "qualifications": list(
                self.qualifications
            ),
        }

    def qualify_many(self, episodes, actions):
        """
        Pair inferred candidate actions with their source episodes and return
        action-aware qualification decisions.

        Returns:
            list of (action, qualification)

        qualification is None only when the source episode cannot be found.
        The coordinator remains responsible only for publication side effects.
        """
        episodes_by_id = {}

        for episode in episodes:
            item = (
                episode.to_dict()
                if hasattr(episode, "to_dict")
                else episode
            )

            episode_id = int(
                item.get("episode_id")
                or 0
            )

            if episode_id > 0:
                episodes_by_id[episode_id] = episode

        qualified = []

        for action in actions:
            episode_id = int(
                getattr(action, "episode_id", 0)
                or 0
            )

            episode = episodes_by_id.get(
                episode_id
            )

            if episode is None:
                qualified.append(
                    (action, None)
                )
                continue

            qualified.append(
                (
                    action,
                    self.qualify(
                        episode,
                        action,
                    ),
                )
            )

        return qualified

    def qualify(self, episode, action):
        item = (
            episode.to_dict()
            if hasattr(episode, "to_dict")
            else dict(episode)
        )

        evidence = list(
            getattr(action, "evidence", None)
            or []
        )

        action_name = str(
            getattr(action, "action", None)
            or "UNKNOWN"
        )

        evidence_mature = bool(
            item.get("evidence_mature", False)
        )

        # First evidence-gating enforcement.
        #
        # The nine-hand golden corpus contains five inferred actions without
        # quantitative stack evidence, and every one of them is UNKNOWN.
        #
        # Retire only that proven class for now. Do not make assumptions about
        # non-chip actions such as CHECK/FOLD or forced posts merely because
        # they lack STACK_CHANGED evidence.
        if (
            action_name == "UNKNOWN"
            and not evidence_mature
        ):
            publish = False
            qualification_reason = (
                "retire_immature_unknown"
            )
        else:
            publish = True
            qualification_reason = (
                "publish_candidate_action"
            )

        qualification = ActionQualification(
            episode_id=int(
                item.get("episode_id")
                or 0
            ),
            seat=str(
                getattr(action, "seat", None)
                or item.get("seat")
                or "unknown"
            ),
            street=str(
                getattr(action, "street", None)
                or item.get("street")
                or "unknown"
            ),
            action=action_name,
            confidence=float(
                getattr(action, "confidence", 0.0)
                or 0.0
            ),
            evidence=evidence,
            evidence_mature=evidence_mature,
            maturity_reason=str(
                item.get("maturity_reason")
                or "unknown"
            ),
            publish=publish,
            qualification_reason=(
                qualification_reason
            ),
        )

        self.qualifications.append(
            qualification.to_dict()
        )

        return qualification
