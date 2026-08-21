from src.observer.action_episode_manager import ActionEpisode

ep = ActionEpisode(
    episode_id=1,
    seat="hero",
    street="PREFLOP",
)

ep.close("idle_timeout")

data = ep.to_dict()

assert data["closed"] is True
assert data["ended_ts"] is not None
assert data["ended_ts"] >= data["started_ts"]

print(
    "Episode serialization regression passed:",
    round(data["ended_ts"] - data["started_ts"], 3),
)
