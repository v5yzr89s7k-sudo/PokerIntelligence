from pathlib import Path

from src.api.snapshot_cache import (
    MAX_HASH_DISTANCE,
    _hash_distance,
    image_hash,
)
from src.api.table_snapshot_reader_core_v2 import (
    _cache_fingerprint_image,
    _prepare,
)


CAPTURE_DIR = Path("runtime/window_captures")


def prepared_cards(frame):
    _, cards = _prepare(frame)
    return {
        card["seat"]: card
        for card in cards
    }


def fingerprint(card):
    image = _cache_fingerprint_image(card)

    if image is None or image.size == 0:
        raise RuntimeError(
            f"empty cache fingerprint for {card['seat']}"
        )

    return image_hash(image)


def main():
    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    )

    if len(captures) < 2:
        raise SystemExit(
            "Need at least two runtime captures."
        )

    first_frame = captures[-2]
    second_frame = captures[-1]

    first_cards = prepared_cards(first_frame)
    second_cards = prepared_cards(second_frame)

    seats = sorted(
        set(first_cards) | set(second_cards)
    )

    print("Snapshot cache fingerprint profile")
    print("=" * 72)
    print("first:", first_frame.name)
    print("second:", second_frame.name)
    print("threshold:", MAX_HASH_DISTANCE)
    print()

    hits = 0
    misses = 0
    appeared = 0
    disappeared = 0

    for seat in seats:
        first = first_cards.get(seat)
        second = second_cards.get(seat)

        if first is None:
            appeared += 1
            print(
                f"{seat:20} APPEARED "
                f"occupied={second['occupied']}"
            )
            continue

        if second is None:
            disappeared += 1
            print(
                f"{seat:20} DISAPPEARED "
                f"occupied={first['occupied']}"
            )
            continue

        first_hash = fingerprint(first)
        second_hash = fingerprint(second)
        distance = _hash_distance(
            first_hash,
            second_hash,
        )

        cache_hit = (
            distance <= MAX_HASH_DISTANCE
        )

        if cache_hit:
            hits += 1
        else:
            misses += 1

        print(
            f"{seat:20} "
            f"distance={distance:2d} "
            f"{'HIT ' if cache_hit else 'MISS'} "
            f"occupied="
            f"{first['occupied']}"
            f"->{second['occupied']}"
        )

    print()
    print("=" * 72)
    print("hits:", hits)
    print("misses:", misses)
    print("appeared:", appeared)
    print("disappeared:", disappeared)
    print(
        "comparable seats:",
        hits + misses,
    )

    comparable = hits + misses

    if comparable:
        print(
            "hit rate:",
            f"{hits / comparable * 100.0:.1f}%",
        )


if __name__ == "__main__":
    main()
