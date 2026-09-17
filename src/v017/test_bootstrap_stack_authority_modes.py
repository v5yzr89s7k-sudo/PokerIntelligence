import numpy as np

from src.bootstrap.hero_bootstrap import (
    bootstrap_local_stacks,
)


GEOMETRY = {
    "stack_regions": {
        "hero": {
            "x": 0,
            "y": 0,
            "width": 1,
            "height": 1,
        },
        "villain": {
            "x": 0,
            "y": 0,
            "width": 1,
            "height": 1,
        },
    }
}


class DummyImage:
    pass


def crop(_image, _rect):
    return np.zeros(
        (2, 2, 3),
        dtype=np.uint8,
    )


def run_case(result):
    def reader(_crop):
        return dict(result)

    rows = bootstrap_local_stacks(
        canonical_image=DummyImage(),
        frozen_participants=[
            "hero",
            "villain",
        ],
        geometry=GEOMETRY,
        crop_geometry_region=crop,
        stack_reader=reader,
    )

    return {
        row["seat"]: row.get(
            "stack_bb"
        )
        for row in rows
    }


def main():
    consensus = run_case({
        "stack_bb": 40.0,
        "confidence": 0.98,
        "votes": 2,
        "mode": "agreement_verified",
        "raw": [],
    })

    assert consensus == {
        "hero": 40.0,
        "villain": 40.0,
    }

    native = run_case({
        "stack_bb": 41.0,
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
        "raw": [],
    })

    assert native == {
        "hero": 41.0,
        "villain": 41.0,
    }

    # Old Hero-only green_only exception must no longer create
    # bootstrap authority.
    weak = run_case({
        "stack_bb": 42.0,
        "confidence": 0.80,
        "votes": 1,
        "mode": "green_only",
        "raw": [],
    })

    assert weak == {
        "hero": None,
        "villain": None,
    }

    print(
        "V0.17 BOOTSTRAP STACK AUTHORITY MODES: PASS"
    )


if __name__ == "__main__":
    main()
