import json
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def score_timeline(timeline):
    items = timeline.get("items", []) if timeline else []

    type_counts = Counter(item.get("type") for item in items)
    street_counts = Counter(item.get("street") for item in items)

    board_counts = [
        item.get("payload", {}).get("board_count")
        for item in items
        if item.get("type") == "board_changed"
    ]

    noisy_board_counts = [
        c for c in board_counts
        if c not in (0, 3, 4, 5)
    ]

    stack_by_frame_ts = defaultdict(int)
    for item in items:
        if item.get("type") == "stack_changed":
            stack_by_frame_ts[item.get("ts")] += 1

    mass_stack_change_frames = {
        str(ts): count
        for ts, count in stack_by_frame_ts.items()
        if count >= 4
    }

    return {
        "total_observations": len(items),
        "type_counts": dict(type_counts),
        "street_counts": dict(street_counts),
        "hero_card_observations": type_counts.get("hero_cards_visible", 0),
        "board_changed_count": type_counts.get("board_changed", 0),
        "board_counts_seen": board_counts,
        "noisy_board_counts": noisy_board_counts,
        "stack_changed_count": type_counts.get("stack_changed", 0),
        "mass_stack_change_frames": mass_stack_change_frames,
        "mass_stack_change_frame_count": len(mass_stack_change_frames),
    }


def score_episodes(episodes):
    if not episodes:
        return {
            "active_count": 0,
            "closed_count": 0,
            "high_confidence_closed": 0,
            "low_confidence_closed": 0,
        }

    closed = episodes.get("closed", []) or episodes.get("closed_tail", []) or []

    high = [
        ep for ep in closed
        if float(ep.get("confidence", 0)) >= 0.75
    ]
    low = [
        ep for ep in closed
        if float(ep.get("confidence", 0)) < 0.75
    ]

    return {
        "active_count": episodes.get("active_count", 0),
        "closed_count": episodes.get("closed_count", len(closed)),
        "high_confidence_closed": len(high),
        "low_confidence_closed": len(low),
    }


def build_scorecard(runtime_dir="runtime/live"):
    runtime = Path(runtime_dir)

    timeline = load_json(runtime / "current_observation_timeline.json")
    episodes = load_json(runtime / "current_action_episodes.json")

    return {
        "timeline": score_timeline(timeline),
        "episodes": score_episodes(episodes),
    }


def print_scorecard(scorecard):
    timeline = scorecard["timeline"]
    episodes = scorecard["episodes"]

    print("PERCEPTION SCORECARD")
    print("--------------------")
    print(f"Total observations: {timeline['total_observations']}")
    print(f"Hero card observations: {timeline['hero_card_observations']}")
    print(f"Board changed observations: {timeline['board_changed_count']}")
    print(f"Noisy board counts: {timeline['noisy_board_counts']}")
    print(f"Stack changed observations: {timeline['stack_changed_count']}")
    print(f"Mass stack-change frames: {timeline['mass_stack_change_frame_count']}")
    print(f"Active episodes: {episodes['active_count']}")
    print(f"Closed episodes: {episodes['closed_count']}")
    print(f"High-confidence closed episodes: {episodes['high_confidence_closed']}")
    print(f"Low-confidence closed episodes: {episodes['low_confidence_closed']}")


if __name__ == "__main__":
    scorecard = build_scorecard()
    print_scorecard(scorecard)
