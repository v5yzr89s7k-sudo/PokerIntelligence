from typing import Any, Callable, Dict, Iterable, List


STREET_RANK = {
    "WAITING": -1,
    "PREFLOP": 0,
    "FLOP": 1,
    "TURN": 2,
    "RIVER": 3,
    "SHOWDOWN": 4,
    "COMPLETE": 5,
    "UNKNOWN": 99,
}


class StreetEpisodeScheduler:
    """
    Preserve chronological poker order between closed action episodes.

    The scheduler does not infer poker actions. It decides only which closed
    episodes may be passed to ActionInferenceEngine.

    Core rule:
    A newer closed episode may not overtake an older closed episode that is
    still waiting for required context.

    Episodes already processed by the inference engine are ignored.
    """

    @staticmethod
    def _episode_dict(episode: Any) -> Dict:
        if isinstance(episode, dict):
            return episode

        if hasattr(episode, "to_dict"):
            return episode.to_dict()

        raise TypeError(
            "episode must be an ActionEpisode or dictionary"
        )

    @classmethod
    def _sort_key(cls, episode: Any):
        item = cls._episode_dict(episode)

        street = str(
            item.get("street") or "UNKNOWN"
        ).upper()

        started_ts = float(
            item.get("started_ts") or 0.0
        )

        episode_id = int(
            item.get("episode_id") or 0
        )

        return (
            started_ts,
            STREET_RANK.get(street, 99),
            episode_id,
        )

    def release(
        self,
        episodes: Iterable[Any],
        *,
        ready_for_inference: Callable[[Any], bool],
        processed_episode_ids=None,
    ) -> List[Any]:
        """
        Release the contiguous ready prefix of closed, unprocessed episodes.

        Once the first unresolved older episode is encountered, every newer
        episode remains blocked, even if the newer episode is independently
        ready.
        """
        processed = set(processed_episode_ids or [])

        candidates = []

        for episode in episodes:
            item = self._episode_dict(episode)
            episode_id = int(
                item.get("episode_id") or 0
            )

            if episode_id <= 0:
                continue

            if episode_id in processed:
                continue

            if not bool(item.get("closed", True)):
                continue

            candidates.append(episode)

        candidates.sort(key=self._sort_key)

        released = []

        for episode in candidates:
            if not ready_for_inference(episode):
                break

            released.append(episode)

        return released

    def status(
        self,
        episodes: Iterable[Any],
        *,
        ready_for_inference: Callable[[Any], bool],
        processed_episode_ids=None,
    ) -> Dict:
        """
        Return diagnostics describing released and blocked episodes.
        """
        processed = set(processed_episode_ids or [])

        candidates = []

        for episode in episodes:
            item = self._episode_dict(episode)
            episode_id = int(
                item.get("episode_id") or 0
            )

            if episode_id <= 0:
                continue

            if episode_id in processed:
                continue

            if not bool(item.get("closed", True)):
                continue

            candidates.append(episode)

        candidates.sort(key=self._sort_key)

        released = self.release(
            candidates,
            ready_for_inference=ready_for_inference,
            processed_episode_ids=processed,
        )

        released_ids = {
            int(
                self._episode_dict(episode).get(
                    "episode_id"
                ) or 0
            )
            for episode in released
        }

        waiting = []
        blocked = []
        barrier_seen = False

        for episode in candidates:
            item = self._episode_dict(episode)

            summary = {
                "episode_id": int(
                    item.get("episode_id") or 0
                ),
                "seat": item.get("seat") or "unknown",
                "street": str(
                    item.get("street") or "UNKNOWN"
                ).upper(),
                "started_ts": float(
                    item.get("started_ts") or 0.0
                ),
                "ready": bool(
                    ready_for_inference(episode)
                ),
            }

            if summary["episode_id"] in released_ids:
                continue

            if not barrier_seen and not summary["ready"]:
                waiting.append(summary)
                barrier_seen = True
            else:
                blocked.append(summary)

        earliest_pending_street = None

        if waiting:
            earliest_pending_street = waiting[0]["street"]
        elif blocked:
            earliest_pending_street = blocked[0]["street"]

        return {
            "earliest_pending_street": earliest_pending_street,
            "released": [
                {
                    "episode_id": int(
                        self._episode_dict(episode).get(
                            "episode_id"
                        ) or 0
                    ),
                    "seat": (
                        self._episode_dict(episode).get(
                            "seat"
                        )
                        or "unknown"
                    ),
                    "street": str(
                        self._episode_dict(episode).get(
                            "street"
                        )
                        or "UNKNOWN"
                    ).upper(),
                }
                for episode in released
            ],
            "waiting": waiting,
            "blocked": blocked,
        }
