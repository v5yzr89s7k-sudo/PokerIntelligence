import unittest

from src.observer.street_episode_scheduler import (
    StreetEpisodeScheduler,
)


def episode(
    episode_id,
    street,
    started_ts,
    *,
    ready=True,
    closed=True,
    seat=None,
):
    return {
        "episode_id": episode_id,
        "seat": seat or f"seat_{episode_id}",
        "street": street,
        "started_ts": started_ts,
        "closed": closed,
        "ready": ready,
    }


def is_ready(item):
    if hasattr(item, "to_dict"):
        item = item.to_dict()

    return bool(item.get("ready"))


class StreetEpisodeSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = StreetEpisodeScheduler()

    def test_releases_ready_episodes_in_timestamp_order(self):
        episodes = [
            episode(3, "PREFLOP", 103.0),
            episode(1, "PREFLOP", 101.0),
            episode(2, "PREFLOP", 102.0),
        ]

        released = self.scheduler.release(
            episodes,
            ready_for_inference=is_ready,
        )

        self.assertEqual(
            [item["episode_id"] for item in released],
            [1, 2, 3],
        )

    def test_unready_older_episode_blocks_newer_ready_episode(self):
        episodes = [
            episode(
                1,
                "PREFLOP",
                101.0,
                ready=False,
            ),
            episode(
                2,
                "PREFLOP",
                102.0,
                ready=True,
            ),
        ]

        released = self.scheduler.release(
            episodes,
            ready_for_inference=is_ready,
        )

        self.assertEqual(released, [])

        status = self.scheduler.status(
            episodes,
            ready_for_inference=is_ready,
        )

        self.assertEqual(
            [item["episode_id"] for item in status["waiting"]],
            [1],
        )
        self.assertEqual(
            [item["episode_id"] for item in status["blocked"]],
            [2],
        )

    def test_preflop_barrier_blocks_flop_episode(self):
        episodes = [
            episode(
                10,
                "PREFLOP",
                200.0,
                ready=False,
                seat="seat_top",
            ),
            episode(
                11,
                "FLOP",
                210.0,
                ready=True,
                seat="hero",
            ),
        ]

        released = self.scheduler.release(
            episodes,
            ready_for_inference=is_ready,
        )

        self.assertEqual(released, [])

        status = self.scheduler.status(
            episodes,
            ready_for_inference=is_ready,
        )

        self.assertEqual(
            status["earliest_pending_street"],
            "PREFLOP",
        )
        self.assertEqual(
            status["blocked"][0]["street"],
            "FLOP",
        )

    def test_contiguous_ready_prefix_is_released(self):
        episodes = [
            episode(1, "PREFLOP", 101.0),
            episode(2, "PREFLOP", 102.0),
            episode(
                3,
                "PREFLOP",
                103.0,
                ready=False,
            ),
            episode(4, "FLOP", 104.0),
        ]

        released = self.scheduler.release(
            episodes,
            ready_for_inference=is_ready,
        )

        self.assertEqual(
            [item["episode_id"] for item in released],
            [1, 2],
        )

    def test_processed_episode_does_not_block_queue(self):
        episodes = [
            episode(
                1,
                "PREFLOP",
                101.0,
                ready=False,
            ),
            episode(
                2,
                "PREFLOP",
                102.0,
                ready=True,
            ),
        ]

        released = self.scheduler.release(
            episodes,
            ready_for_inference=is_ready,
            processed_episode_ids={1},
        )

        self.assertEqual(
            [item["episode_id"] for item in released],
            [2],
        )

    def test_open_episode_is_ignored_until_closed(self):
        episodes = [
            episode(
                1,
                "PREFLOP",
                101.0,
                ready=False,
                closed=False,
            ),
            episode(
                2,
                "PREFLOP",
                102.0,
                ready=True,
            ),
        ]

        released = self.scheduler.release(
            episodes,
            ready_for_inference=is_ready,
        )

        self.assertEqual(
            [item["episode_id"] for item in released],
            [2],
        )


if __name__ == "__main__":
    unittest.main()
