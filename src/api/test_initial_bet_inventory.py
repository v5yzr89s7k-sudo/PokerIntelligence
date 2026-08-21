import numpy as np

import src.api.api_event_coordinator as coord


def main():
    old_classifier = coord.bet_region_occupancy
    old_queue = coord.queue_bet_amount_request
    old_canonicalizer = coord.to_canonical_frame

    calls = []

    try:
        # Keep the synthetic frame untouched.
        coord.to_canonical_frame = (
            lambda frame, _geometry: frame
        )

        # Ground-truth-style static classification:
        #
        # opponent UTG-looking region = occupied
        # opponent empty region       = empty
        # Hero                        = falsely static-positive, must be ignored
        coord.bet_region_occupancy = (
            lambda *_args, **_kwargs: {
                "seat_lower_left": {
                    "legacy_occupied": True,
                },
                "seat_lower_right": {
                    "legacy_occupied": False,
                },
                "hero": {
                    "legacy_occupied": True,
                },
                "seat_mid_left": {
                    "legacy_occupied": False,
                },
            }
        )

        def fake_queue(
            state,
            frame,
            seat,
            street,
            source="transition",
        ):
            calls.append({
                "frame": str(frame),
                "seat": seat,
                "street": street,
                "source": source,
            })
            return state

        coord.queue_bet_amount_request = fake_queue

        state = coord.fresh_state()
        state["hand_token"] = "initial-test"
        state["phase"] = "PREFLOP"

        frame = np.zeros(
            (696, 934, 3),
            dtype=np.uint8,
        )

        state = coord.queue_initial_bet_inventory(
            state,
            frame,
            "frame_0001.png",
        )

        assert (
            state["initial_bet_inventory_done"]
            is True
        )

        assert calls == [{
            "frame": "frame_0001.png",
            "seat": "seat_lower_left",
            "street": "PREFLOP",
            "source": "initial_inventory",
        }]

        # Prove strict one-shot behavior.
        state = coord.queue_initial_bet_inventory(
            state,
            frame,
            "frame_0002.png",
        )

        assert len(calls) == 1

        print(
            "PASS initial bet inventory: "
            "static-positive opponent queued once; "
            "Hero excluded; source=initial_inventory"
        )

    finally:
        coord.bet_region_occupancy = old_classifier
        coord.queue_bet_amount_request = old_queue
        coord.to_canonical_frame = old_canonicalizer


if __name__ == "__main__":
    main()
