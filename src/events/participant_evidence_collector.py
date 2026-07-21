from time import time

from src.events.participant_freezer import ParticipantFreezer
from src.events.participant_evidence_store import (
    PARTICIPANT_EVIDENCE_PATH,
    write_evidence,
)


class ParticipantEvidenceCollector:
    """
    Collect live hand-start card-back evidence in the capture process and
    publish it for the asynchronous snapshot worker.
    """

    def __init__(self, evidence_path=PARTICIPANT_EVIDENCE_PATH):
        self.evidence_path = evidence_path
        self.hand_token = ""
        self.freezer = None

    def reset(self, hand_token, started_ts=None):
        self.hand_token = str(hand_token or "")
        self.freezer = ParticipantFreezer()
        self.freezer.reset(
            started_ts=started_ts or time(),
        )

        self.publish()
        return self.snapshot()

    def observe(
        self,
        frame,
        geometry,
        hand_token,
        frame_path="",
        started_ts=None,
    ):
        token = str(hand_token or "")

        if not token:
            return None

        if self.freezer is None or token != self.hand_token:
            self.reset(
                token,
                started_ts=started_ts,
            )

        self.freezer.observe(
            frame,
            geometry,
            frame_path=frame_path,
        )

        snapshot = self.freezer.snapshot()
        frame_count = int(
            snapshot.get("frame_count") or 0
        )

        # Freeze the process-lifetime collector immediately when the
        # minimum temporal evidence requirement is satisfied. This keeps
        # the shared evidence immutable and prevents late seat arrivals
        # from entering the current hand.
        if (
            frame_count >= 6
            and not snapshot.get("frozen")
        ):
            self.freezer.freeze(
                hero_is_dealt=True,
                frozen_ts=time(),
            )
            snapshot = self.freezer.snapshot()

            print(
                "[PARTICIPANT_AUTO_FREEZE]",
                f"frames={snapshot.get('frame_count')}",
                f"seats={snapshot.get('dealt_in_seats')}",
                flush=True,
            )

        self.publish()
        return self.snapshot()

    def freeze(self, hand_token, frozen_ts=None):
        token = str(hand_token or "")

        if (
            not token
            or self.freezer is None
            or token != self.hand_token
        ):
            return []

        evidence = self.freezer.snapshot()
        frame_count = int(
            evidence.get("frame_count") or 0
        )

        # Never convert incomplete temporal evidence into an immutable
        # dealt-in roster. The capture loop must remain free to collect
        # additional frames after the Hero API result arrives.
        if frame_count < 6:
            print(
                "[PARTICIPANT_FREEZE_DEFER]",
                f"frames={frame_count}",
                "minimum=6",
                flush=True,
            )
            self.publish()
            return []

        seats = self.freezer.freeze(
            hero_is_dealt=True,
            frozen_ts=frozen_ts or time(),
        )

        self.publish()
        return seats

    def snapshot(self):
        if self.freezer is None:
            return {
                "hand_token": self.hand_token,
                "frame_count": 0,
                "frozen": False,
                "dealt_in_seats": [],
            }

        evidence = self.freezer.snapshot()
        evidence["hand_token"] = self.hand_token
        evidence["updated_ts"] = time()
        return evidence

    def publish(self):
        evidence = self.snapshot()
        write_evidence(
            self.evidence_path,
            evidence,
        )
        return evidence
