from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "runtime" / "golden_hands"

CHRONOLOGY_TYPES = {
    "actor_observed",
    "physical_actor_completed",
}

QUANTITATIVE_TYPES = {
    "inferred_action",
}

def load_events(hand):
    path = GOLDEN / hand / "api_events.jsonl"
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]

def classify(hand):
    events = load_events(hand)
    types = [event.get("type") for event in events]

    inferred = [
        event
        for event in events
        if event.get("type") in QUANTITATIVE_TYPES
    ]

    chronology = [
        event
        for event in events
        if event.get("type") in CHRONOLOGY_TYPES
    ]

    boards = [
        event
        for event in events
        if event.get("type") == "board"
    ]

    return {
        "hand": hand,
        "event_count": len(events),
        "inferred_count": len(inferred),
        "chronology_count": len(chronology),
        "board_count": len(boards),
        "has_quantitative_without_chronology": (
            bool(inferred) and not chronology
        ),
        "types": types,
    }

def main():
    hands = sorted(
        path.name
        for path in GOLDEN.glob("hand_*")
        if path.is_dir()
        and (path / "api_events.jsonl").exists()
    )

    rows = [classify(hand) for hand in hands]

    print("===== GOLDEN EVENT SCHEMA MATRIX =====")
    print()

    for row in rows:
        print(
            f"{row['hand']}: "
            f"events={row['event_count']} "
            f"inferred={row['inferred_count']} "
            f"chronology={row['chronology_count']} "
            f"boards={row['board_count']} "
            f"legacy_quantitative_only="
            f"{row['has_quantitative_without_chronology']}"
        )

    print()
    print("===== FAILING-HAND LEGACY CHECK =====")

    expected_legacy = {
        "hand_0001",
        "hand_0002",
        "hand_0003",
        "hand_0004",
        "hand_0005",
        "hand_0006",
        "hand_0007",
    }

    actual_legacy = {
        row["hand"]
        for row in rows
        if row["has_quantitative_without_chronology"]
    }

    print("expected legacy:", sorted(expected_legacy))
    print("actual legacy  :", sorted(actual_legacy))

    missing = expected_legacy - actual_legacy
    extra = actual_legacy - expected_legacy

    if missing:
        print("NOTE: failing hands without this signature:", sorted(missing))

    if extra:
        print("NOTE: additional legacy fixtures:", sorted(extra))

    hand2 = classify("hand_0002")

    assert hand2["inferred_count"] > 0, (
        "hand_0002 must contain historical quantitative actions"
    )

    assert hand2["chronology_count"] == 0, (
        "hand_0002 unexpectedly contains current chronology events"
    )

    print()
    print(
        "PASS: hand_0002 proves legacy quantitative-action "
        "schema without current chronology transport"
    )

    hand8 = classify("hand_0008")

    assert hand8["inferred_count"] == 0, (
        "passing hand_0008 unexpectedly exercises inferred-action path"
    )

    print(
        "PASS: hand_0008 is not a control for the "
        "quantitative chronology contract"
    )

    print()
    print("CLASSIFICATION: A")
    print(
        "Historical golden event streams predate the current "
        "chronology/admission transport."
    )
    print(
        "Production chronology must NOT be weakened to make "
        "legacy fixtures pass."
    )

if __name__ == "__main__":
    main()
