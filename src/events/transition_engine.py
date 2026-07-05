class BooleanTransitionTracker:
    def __init__(self):
        self.previous = {}

    def update(self, name, current):
        prev_known = name in self.previous
        prev = bool(self.previous.get(name, False))
        curr = bool(current)

        self.previous[name] = curr

        return {
            "name": name,
            "previous_known": prev_known,
            "previous": prev,
            "current": curr,
            "appeared": prev_known and (not prev) and curr,
            "cleared": prev_known and prev and (not curr),
            "changed": prev_known and prev != curr,
        }


class TransitionEngine:
    def __init__(self):
        self.bool_tracker = BooleanTransitionTracker()

    def apply(self, changes):
        hero_cards = self.bool_tracker.update(
            "hero_cards_visible",
            getattr(changes, "hero_cards_visible", False),
        )

        changes.hero_cards_transition = hero_cards
        changes.hero_cards_appeared = hero_cards["appeared"]
        changes.hero_cards_cleared = hero_cards["cleared"]

        return changes
