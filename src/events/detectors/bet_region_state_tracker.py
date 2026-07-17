import time


class BetRegionStateTracker:
    """
    Converts noisy raw bet-region occupancy into confirmed transitions.

    The first frame establishes a baseline and never emits transitions.
    Later changes must persist for the configured confirmation period
    before appeared=True or cleared=True is emitted.
    """

    def __init__(
        self,
        confirm_on_seconds=0.15,
        confirm_off_seconds=0.15,
        clock=None,
    ):
        self.confirm_on_seconds = float(confirm_on_seconds)
        self.confirm_off_seconds = float(confirm_off_seconds)
        self.clock = clock or time.monotonic

        self.initialized = False
        self.confirmed = {}
        self.candidate_state = {}
        self.candidate_since = {}
        self.occupied_since = {}

    def reset(self):
        self.initialized = False
        self.confirmed.clear()
        self.candidate_state.clear()
        self.candidate_since.clear()
        self.occupied_since.clear()

    def _result(
        self,
        info,
        previous_confirmed,
        current_confirmed,
        appeared=False,
        cleared=False,
        now=None,
        candidate=None,
    ):
        now = self.clock() if now is None else now

        occupied_since = self.occupied_since.get(info.get("_seat"))
        occupied_duration_ms = 0.0

        if current_confirmed and occupied_since is not None:
            occupied_duration_ms = max(
                0.0,
                (now - occupied_since) * 1000.0,
            )

        payload = {
            key: value
            for key, value in info.items()
            if key != "_seat"
        }

        payload.update({
            # Expose confirmed occupancy to downstream consumers.
            "occupied": current_confirmed,
            "raw_occupied": bool(info.get("occupied", False)),
            "previous_occupied": previous_confirmed,
            "current_occupied": current_confirmed,
            "candidate_state": candidate,
            "appeared": appeared,
            "cleared": cleared,
            "changed": appeared or cleared,
            "occupied_duration_ms": round(
                occupied_duration_ms,
                1,
            ),
        })

        return payload

    def update(self, occupancy):
        now = self.clock()
        transitions = {}

        # First frame is baseline only. Existing chips or static graphics
        # must not be emitted as newly appeared actions.
        if not self.initialized:
            for seat, raw_info in occupancy.items():
                info = dict(raw_info or {})
                raw = bool(info.get("occupied", False))

                self.confirmed[seat] = raw
                self.candidate_state[seat] = None
                self.candidate_since[seat] = None

                if raw:
                    self.occupied_since[seat] = now

                info["_seat"] = seat
                transitions[seat] = self._result(
                    info,
                    previous_confirmed=raw,
                    current_confirmed=raw,
                    appeared=False,
                    cleared=False,
                    now=now,
                    candidate=None,
                )

            self.initialized = True
            return transitions

        seats = (
            set(self.confirmed.keys())
            | set(occupancy.keys())
        )

        for seat in seats:
            info = dict(occupancy.get(seat, {}) or {})
            info["_seat"] = seat

            raw = bool(info.get("occupied", False))
            confirmed = bool(self.confirmed.get(seat, False))
            candidate = self.candidate_state.get(seat)
            candidate_since = self.candidate_since.get(seat)

            appeared = False
            cleared = False

            if raw == confirmed:
                # Signal returned to its confirmed state before debounce
                # completed, so cancel any pending candidate.
                candidate = None
                candidate_since = None

            else:
                if candidate != raw:
                    candidate = raw
                    candidate_since = now
                else:
                    required = (
                        self.confirm_on_seconds
                        if raw
                        else self.confirm_off_seconds
                    )

                    if (
                        candidate_since is not None
                        and now - candidate_since >= required
                    ):
                        previous = confirmed
                        confirmed = raw
                        candidate = None
                        candidate_since = None

                        appeared = (not previous) and confirmed
                        cleared = previous and (not confirmed)

                        if appeared:
                            self.occupied_since[seat] = now
                        elif cleared:
                            self.occupied_since.pop(seat, None)

            self.confirmed[seat] = confirmed
            self.candidate_state[seat] = candidate
            self.candidate_since[seat] = candidate_since

            transitions[seat] = self._result(
                info,
                previous_confirmed=(
                    not confirmed
                    if appeared or cleared
                    else confirmed
                ),
                current_confirmed=confirmed,
                appeared=appeared,
                cleared=cleared,
                now=now,
                candidate=candidate,
            )

        return transitions
