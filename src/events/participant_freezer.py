from copy import deepcopy
from time import time

from src.events.detectors.card_presence import (
    SEAT_ORDER,
    crop,
    opponent_card_back_score,
)


class ParticipantFreezer:
    """
    Aggregate hand-start hole-card evidence across multiple frames, then
    freeze one immutable dealt-in roster for the duration of the hand.
    """

    def __init__(self, threshold=0.0):
        self.threshold = float(threshold)
        self.reset()

    def reset(self, started_ts=None):
        self.started_ts = float(started_ts or time())
        self.frozen = False
        self.frame_count = 0
        self.frozen_ts = None

        self.max_scores = {
            seat: {
                "card_1": 0.0,
                "card_2": 0.0,
            }
            for seat in SEAT_ORDER
        }

        self.max_frames = {
            seat: {
                "card_1": "",
                "card_2": "",
            }
            for seat in SEAT_ORDER
        }

        # Shadow temporal evidence. These counters do not change the
        # authoritative freeze decision yet. They let us measure whether a
        # seat was detected consistently or only in one isolated frame.
        self.positive_frames = {
            seat: {
                "card_1": 0,
                "card_2": 0,
            }
            for seat in SEAT_ORDER
        }

        self.paired_positive_frames = {
            seat: 0
            for seat in SEAT_ORDER
        }

        self._dealt_in_seats = []
        return self

    def observe(self, frame, geometry, frame_path=""):
        if self.frozen:
            return self.snapshot()

        hole_cards = geometry.get("hole_cards") or {}
        self.frame_count += 1

        for seat in SEAT_ORDER:
            # Hero is guaranteed by the hero_cards event and is handled
            # explicitly during freeze. Opponent evidence must use the
            # calibrated red ACR card-back classifier, not generic brightness.
            if seat == "hero":
                continue

            regions = hole_cards.get(seat) or {}
            frame_present = {
                "card_1": False,
                "card_2": False,
            }

            for card_name in ("card_1", "card_2"):
                rect = regions.get(card_name)

                if not rect:
                    score = 0.0
                    present = False
                else:
                    result = opponent_card_back_score(
                        crop(frame, rect)
                    )
                    present = bool(result.get("present"))
                    score = float(
                        result.get("red_ratio") or 0.0
                    )

                    # A score is valid only when the complete calibrated
                    # classifier agrees that a red ACR card back is present.
                    if not present:
                        score = 0.0

                frame_present[card_name] = present

                if present:
                    self.positive_frames[seat][card_name] += 1

                if score > self.max_scores[seat][card_name]:
                    self.max_scores[seat][card_name] = score
                    self.max_frames[seat][card_name] = str(
                        frame_path or ""
                    )

            if (
                frame_present["card_1"]
                and frame_present["card_2"]
            ):
                self.paired_positive_frames[seat] += 1

        return self.snapshot()

    def freeze(self, hero_is_dealt=True, frozen_ts=None):
        if self.frozen:
            return list(self._dealt_in_seats)

        dealt_in = []

        for seat in SEAT_ORDER:
            if seat == "hero":
                if hero_is_dealt:
                    dealt_in.append(seat)
                continue

            card_1 = self.max_scores[seat]["card_1"]
            card_2 = self.max_scores[seat]["card_2"]

            if (
                card_1 > self.threshold
                and card_2 > self.threshold
            ):
                dealt_in.append(seat)

        self._dealt_in_seats = dealt_in
        self.frozen = True
        self.frozen_ts = float(frozen_ts or time())

        return list(self._dealt_in_seats)

    def stable_dealt_in_seats(
        self,
        hero_is_dealt=True,
        minimum_card_hits=2,
        minimum_paired_hits=1,
    ):
        """
        Return a shadow temporal roster without freezing the participant set.

        This is telemetry only. The authoritative freeze continues to use
        max_scores until live evidence proves a better rule.
        """
        stable = []

        for seat in SEAT_ORDER:
            if seat == "hero":
                if hero_is_dealt:
                    stable.append(seat)
                continue

            card_1_hits = int(
                self.positive_frames[seat]["card_1"]
            )
            card_2_hits = int(
                self.positive_frames[seat]["card_2"]
            )
            paired_hits = int(
                self.paired_positive_frames[seat]
            )

            if (
                card_1_hits >= int(minimum_card_hits)
                and card_2_hits >= int(minimum_card_hits)
                and paired_hits >= int(minimum_paired_hits)
            ):
                stable.append(seat)

        return stable

    def get_dealt_in_seats(self):
        return list(self._dealt_in_seats)

    def restore(self, evidence):
        """
        Restore accumulated evidence published by another process.

        This does not re-run visual detection. It only restores the maxima,
        frame count, lifecycle state, and any already-frozen roster.
        """
        evidence = evidence or {}

        self.started_ts = float(
            evidence.get("started_ts") or time()
        )
        self.frozen = bool(evidence.get("frozen"))
        self.frozen_ts = evidence.get("frozen_ts")
        self.frame_count = int(
            evidence.get("frame_count") or 0
        )

        stored_scores = evidence.get("max_scores") or {}
        stored_frames = evidence.get("max_frames") or {}
        stored_positive_frames = (
            evidence.get("positive_frames") or {}
        )
        stored_paired_frames = (
            evidence.get("paired_positive_frames") or {}
        )

        for seat in SEAT_ORDER:
            seat_scores = stored_scores.get(seat) or {}
            seat_frames = stored_frames.get(seat) or {}
            seat_positive = (
                stored_positive_frames.get(seat) or {}
            )

            for card_name in ("card_1", "card_2"):
                self.max_scores[seat][card_name] = float(
                    seat_scores.get(card_name) or 0.0
                )
                self.max_frames[seat][card_name] = str(
                    seat_frames.get(card_name) or ""
                )
                self.positive_frames[seat][card_name] = int(
                    seat_positive.get(card_name) or 0
                )

            self.paired_positive_frames[seat] = int(
                stored_paired_frames.get(seat) or 0
            )

        self._dealt_in_seats = [
            seat
            for seat in (
                evidence.get("dealt_in_seats") or []
            )
            if seat in SEAT_ORDER
        ]

        return self

    @classmethod
    def from_evidence(cls, evidence):
        freezer = cls(
            threshold=float(
                (evidence or {}).get("threshold") or 0.0
            )
        )
        return freezer.restore(evidence)

    def snapshot(self):
        return {
            "started_ts": self.started_ts,
            "frozen": self.frozen,
            "frozen_ts": self.frozen_ts,
            "frame_count": self.frame_count,
            "threshold": self.threshold,
            "dealt_in_seats": list(self._dealt_in_seats),
            "stable_dealt_in_seats": (
                self.stable_dealt_in_seats()
            ),
            "max_scores": deepcopy(self.max_scores),
            "max_frames": deepcopy(self.max_frames),
            "positive_frames": deepcopy(
                self.positive_frames
            ),
            "paired_positive_frames": deepcopy(
                self.paired_positive_frames
            ),
        }
