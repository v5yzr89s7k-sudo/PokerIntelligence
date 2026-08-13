from pathlib import Path
import json

ROOT = Path("runtime/golden_hands")

terminal = {
    "CANONICAL_ACTION": 0,
    "CANONICAL_SKIP": 0,
    "ACTION_RETIRED": 0,
    "ACTION_DEFERRED": 0,
}

print("=" * 72)
print("ACTION PRESERVATION AUDIT")
print("=" * 72)

for hand in sorted(ROOT.glob("hand_*")):

    events = hand / "api_events.jsonl"

    if not events.exists():
        continue

    inferred = []

    for line in events.read_text().splitlines():

        if not line.strip():
            continue

        event = json.loads(line)

        if event.get("type") != "inferred_action":
            continue

        inferred.append(
            (
                event.get("episode_id"),
                event.get("street"),
                event.get("seat"),
                event.get("action"),
            )
        )

    print()
    print("=" * 72)
    print(hand.name)
    print("=" * 72)

    print(f"Inferred actions: {len(inferred)}")

    for item in inferred:
        print(
            " ",
            f"episode={item[0]}",
            f"street={item[1]}",
            f"seat={item[2]}",
            f"action={item[3]}",
        )

print()
print("=" * 72)
print("NOTE")
print("=" * 72)
print(
    "Next step: correlate every inferred episode_id with the "
    "BettingRoundTracker decision log so every inferred action has "
    "exactly one terminal outcome."
)
