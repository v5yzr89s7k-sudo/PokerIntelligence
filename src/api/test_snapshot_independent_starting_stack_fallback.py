import numpy as np

from src.api import table_snapshot_reader_core_v2 as snapshot


SEAT = "seat_lower_left"


def main():
    region = snapshot.GEOMETRY[
        "stack_regions"
    ][SEAT]

    # Minimal synthetic seat card large enough to contain
    # the real stack geometry relative to its bounds.
    card = {
        "seat": SEAT,
        "image": np.zeros(
            (
                int(region["y"])
                + int(region["height"])
                + 10,
                int(region["x"])
                + int(region["width"])
                + 10,
                3,
            ),
            dtype=np.uint8,
        ),
        "bounds": {
            "x1": 0,
            "y1": 0,
        },
    }

    old_read_stack = snapshot.read_stack
    old_stack_lookup = snapshot.stack_lookup

    had_independent = hasattr(
        snapshot,
        "read_stack_independent_consensus",
    )

    old_independent = getattr(
        snapshot,
        "read_stack_independent_consensus",
        None,
    )

    try:
        snapshot.stack_lookup = (
            lambda cache, seat, crop: None
        )

        # Reproduce Birkam's actual ordinary result:
        # correct selected value, but deliberately untrusted
        # because segmentation disagrees.
        snapshot.read_stack = (
            lambda crop: {
                "stack_bb": 48.57,
                "stack_text": "48.57 BB",
                "confidence": 0.50,
                "votes": 1,
                "mode": "segmentation_disagreement",
                "raw": [
                    {
                        "variant": "green",
                        "raw": "48.57 BB",
                        "stack_bb": 48.57,
                    },
                    {
                        "variant": "plain",
                        "raw": "48.57 BB",
                        "stack_bb": 48.57,
                    },
                    {
                        "variant": "psm13_t130",
                        "raw": "48.87 BB",
                        "stack_bb": 48.87,
                    },
                ],
            }
        )

        # Reproduce the already-existing independent reader's
        # strong consensus for the same crop.
        snapshot.read_stack_independent_consensus = (
            lambda crop: {
                "stack_bb": 48.57,
                "stack_text": "48.57 BB",
                "confidence": 0.98,
                "votes": 3,
                "mode": "independent_segmentation",
                "raw": [],
            }
        )

        readings, updates, _ = (
            snapshot._read_local_stacks(
                [card],
                {},
            )
        )

        result = readings[SEAT]

        print("result:", result)
        print("cache updates:", updates)

        assert (
            result.get("stack_bb") == 48.57
        ), (
            "REPRODUCED: snapshot discarded strong "
            "independent starting-stack consensus"
        )

        assert (
            result.get("mode")
            == "independent_segmentation"
        ), (
            "REPRODUCED: snapshot did not promote "
            "independent starting-stack evidence"
        )

        assert (
            float(result.get("confidence") or 0)
            >= 0.95
        )

        assert (
            int(result.get("votes") or 0)
            >= 3
        )

        print(
            "PASS: strong independent segmentation "
            "can establish starting stack"
        )

    finally:
        snapshot.read_stack = old_read_stack
        snapshot.stack_lookup = old_stack_lookup

        if had_independent:
            snapshot.read_stack_independent_consensus = (
                old_independent
            )
        else:
            try:
                delattr(
                    snapshot,
                    "read_stack_independent_consensus",
                )
            except AttributeError:
                pass


if __name__ == "__main__":
    main()
