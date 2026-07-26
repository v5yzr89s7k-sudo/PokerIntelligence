from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.table_snapshot_reader_core_v2 import (
    CLIENT,
    _prepare,
    _build_content,
    _extract_json,
    _normalize_result,
)


CAPTURE_DIR = ROOT / "runtime/window_captures"
OUTPUT_DIR = ROOT / "runtime/snapshot_latency_benchmark"
MAX_WORKERS = 8


def request_cards(cards):
    content, image_bytes = _build_content(cards)

    started = perf_counter()

    response = CLIENT.responses.create(
        model="gpt-4.1-mini",
        input=[{
            "role": "user",
            "content": content,
        }],
    )

    api_ms = (perf_counter() - started) * 1000.0

    parse_started = perf_counter()

    data = _extract_json(response.output_text)
    normalized = _normalize_result(
        data,
        cards,
        dealer="",
    )

    parse_ms = (
        perf_counter() - parse_started
    ) * 1000.0

    return {
        "api_ms": round(api_ms, 1),
        "parse_ms": round(parse_ms, 1),
        "image_bytes": image_bytes,
        "players": normalized.get("players") or [],
        "confidence": normalized.get("confidence"),
        "raw_output": response.output_text,
    }


def player_summary(players):
    return {
        player.get("seat"): {
            "name": player.get("name") or "",
            "stack_text": player.get("stack_text") or "",
            "stack_bb": player.get("stack_bb"),
        }
        for player in players
    }


def compare_results(batch_players, parallel_players):
    batch = player_summary(batch_players)
    parallel = player_summary(parallel_players)

    seats = sorted(set(batch) | set(parallel))
    comparison = []

    for seat in seats:
        batch_entry = batch.get(seat) or {}
        parallel_entry = parallel.get(seat) or {}

        comparison.append({
            "seat": seat,
            "batch_name": batch_entry.get("name", ""),
            "parallel_name": parallel_entry.get("name", ""),
            "name_match": (
                batch_entry.get("name", "")
                == parallel_entry.get("name", "")
            ),
            "batch_stack_text": batch_entry.get(
                "stack_text",
                "",
            ),
            "parallel_stack_text": parallel_entry.get(
                "stack_text",
                "",
            ),
            "stack_match": (
                batch_entry.get("stack_text", "")
                == parallel_entry.get("stack_text", "")
            ),
        })

    return comparison


def main():
    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    )

    if not captures:
        raise SystemExit(
            f"No captures found in {CAPTURE_DIR}"
        )

    frame = captures[-1]

    print("Frame:", frame)
    print()

    prepare_started = perf_counter()
    _, cards = _prepare(frame)
    prepare_ms = (
        perf_counter() - prepare_started
    ) * 1000.0

    print(
        f"Prepared {len(cards)} occupied seat cards "
        f"in {prepare_ms:.1f} ms"
    )
    print(
        "Seats:",
        [card["seat"] for card in cards],
    )
    print()

    # --------------------------------------------------------
    # Mode A: one request containing every seat
    # --------------------------------------------------------
    print("==================== MODE A: BATCH ====================")

    batch_wall_started = perf_counter()
    batch_result = request_cards(cards)
    batch_wall_ms = (
        perf_counter() - batch_wall_started
    ) * 1000.0

    print(
        f"Batch wall:  {batch_wall_ms:.1f} ms"
    )
    print(
        f"Batch API:   {batch_result['api_ms']:.1f} ms"
    )
    print(
        f"Batch parse: {batch_result['parse_ms']:.1f} ms"
    )
    print(
        f"Batch images: "
        f"{batch_result['image_bytes'] / 1024:.1f} KB"
    )

    for player in batch_result["players"]:
        print(
            f"  {player.get('seat'):18} "
            f"name={player.get('name')!r:24} "
            f"stack={player.get('stack_text')!r}"
        )

    print()

    # --------------------------------------------------------
    # Mode B: one concurrent request per seat
    # --------------------------------------------------------
    print("==================== MODE B: PARALLEL =================")

    parallel_wall_started = perf_counter()
    seat_results = {}

    with ThreadPoolExecutor(
        max_workers=min(MAX_WORKERS, len(cards))
    ) as executor:
        futures = {
            executor.submit(
                request_cards,
                [card],
            ): card["seat"]
            for card in cards
        }

        for future in as_completed(futures):
            seat = futures[future]

            try:
                result = future.result()
            except Exception as exc:
                seat_results[seat] = {
                    "error": (
                        f"{type(exc).__name__}: {exc}"
                    )
                }
                print(
                    f"  FAIL {seat}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            seat_results[seat] = result

            player = (
                result["players"][0]
                if result["players"]
                else {}
            )

            print(
                f"  DONE {seat:18} "
                f"api={result['api_ms']:7.1f} ms "
                f"name={player.get('name')!r:24} "
                f"stack={player.get('stack_text')!r}"
            )

    parallel_wall_ms = (
        perf_counter() - parallel_wall_started
    ) * 1000.0

    parallel_players = []
    parallel_api_times = []
    parallel_image_bytes = 0
    failures = []

    for card in cards:
        seat = card["seat"]
        result = seat_results.get(seat) or {}

        if result.get("error"):
            failures.append({
                "seat": seat,
                "error": result["error"],
            })
            continue

        parallel_api_times.append(
            float(result["api_ms"])
        )
        parallel_image_bytes += int(
            result["image_bytes"]
        )
        parallel_players.extend(
            result["players"]
        )

    print()
    print(
        f"Parallel wall: {parallel_wall_ms:.1f} ms"
    )

    if parallel_api_times:
        print(
            f"Fastest seat:  "
            f"{min(parallel_api_times):.1f} ms"
        )
        print(
            f"Slowest seat:  "
            f"{max(parallel_api_times):.1f} ms"
        )
        print(
            f"Average seat:  "
            f"{sum(parallel_api_times) / len(parallel_api_times):.1f} ms"
        )

    print(
        f"Parallel images: "
        f"{parallel_image_bytes / 1024:.1f} KB"
    )

    print()
    print("==================== COMPARISON =======================")

    comparison = compare_results(
        batch_result["players"],
        parallel_players,
    )

    for item in comparison:
        print(
            f"{item['seat']:18} "
            f"name_match={str(item['name_match']):5} "
            f"stack_match={str(item['stack_match']):5} "
            f"batch_name={item['batch_name']!r:22} "
            f"parallel_name={item['parallel_name']!r}"
        )

    name_matches = sum(
        1 for item in comparison
        if item["name_match"]
    )
    stack_matches = sum(
        1 for item in comparison
        if item["stack_match"]
    )

    speedup = (
        batch_wall_ms / parallel_wall_ms
        if parallel_wall_ms > 0
        else 0.0
    )

    print()
    print("==================== SUMMARY ==========================")
    print(f"Batch wall:       {batch_wall_ms:.1f} ms")
    print(f"Parallel wall:    {parallel_wall_ms:.1f} ms")
    print(f"Wall speedup:     {speedup:.2f}x")
    print(
        f"Name agreement:   "
        f"{name_matches}/{len(comparison)}"
    )
    print(
        f"Stack agreement:  "
        f"{stack_matches}/{len(comparison)}"
    )
    print(f"Parallel failures:{len(failures)}")

    report = {
        "frame": str(frame),
        "seat_count": len(cards),
        "prepare_ms": round(prepare_ms, 1),
        "batch": {
            **batch_result,
            "wall_ms": round(batch_wall_ms, 1),
        },
        "parallel": {
            "wall_ms": round(
                parallel_wall_ms,
                1,
            ),
            "seat_results": seat_results,
            "players": parallel_players,
            "failures": failures,
        },
        "comparison": comparison,
        "summary": {
            "speedup": round(speedup, 3),
            "name_matches": name_matches,
            "stack_matches": stack_matches,
            "comparison_count": len(comparison),
            "failure_count": len(failures),
        },
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        OUTPUT_DIR
        / "snapshot_api_modes.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2) + "\n"
    )

    print()
    print("Report:", report_path)


if __name__ == "__main__":
    main()
