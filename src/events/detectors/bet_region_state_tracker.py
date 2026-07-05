class BetRegionStateTracker:
    def __init__(self):
        self.previous = {}

    def update(self, occupancy):
        transitions = {}

        seats = set(self.previous.keys()) | set(occupancy.keys())

        for seat in seats:
            prev = bool(self.previous.get(seat, {}).get("occupied", False))
            curr_info = occupancy.get(seat, {}) or {}
            curr = bool(curr_info.get("occupied", False))

            appeared = (not prev) and curr
            cleared = prev and (not curr)

            transitions[seat] = {
                **curr_info,
                "previous_occupied": prev,
                "current_occupied": curr,
                "appeared": appeared,
                "cleared": cleared,
                "changed": appeared or cleared,
            }

        self.previous = dict(occupancy)
        return transitions
