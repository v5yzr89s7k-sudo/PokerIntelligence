"""
V0.17 physical participant-topology freeze.

One occupancy owner:
    native_occupied_seats()

This layer adds temporal stability only. It does not use identity,
stack value, poker position, or simulator truth.
"""


class ParticipantFreeze:

    def __init__(
        self,
        stable_required=3,
    ):
        self.stable_required = int(
            stable_required
        )

        if self.stable_required < 1:
            raise ValueError(
                "stable_required must be >= 1"
            )

        self.candidate = None
        self.streak = 0
        self.frozen = None

        # Latest directly observed trusted local stack value for each
        # physical participant during the pre-acquisition interval.
        #
        # Quantitative evidence does NOT decide topology.
        self.stack_authority = {}

    def observe(
        self,
        participants,
    ):
        participants = tuple(
            participants
        )

        if self.frozen is not None:
            return self.frozen

        if participants == self.candidate:
            self.streak += 1
        else:
            self.candidate = participants
            self.streak = 1

        if (
            "hero" in participants
            and self.streak
            >= self.stable_required
        ):
            self.frozen = participants

        return self.frozen

    def observe_stack_authority(
        self,
        rows,
        *,
        frame=None,
    ):
        """
        Preserve latest trusted physical stack values.

        Caller controls when stack sensing occurs. In live acquisition
        this is invoked only after Hero visibility has already been
        checked false, so it cannot delay Hero acquisition.
        """
        for row in rows:
            seat = row.get("seat")
            value = row.get("stack_bb")

            if (
                not seat
                or value is None
            ):
                continue

            self.stack_authority[
                str(seat)
            ] = {
                "value": float(value),
                "frame": frame,
            }

        return dict(
            self.stack_authority
        )

    @property
    def trusted_stacks(self):
        return {
            seat: float(
                evidence["value"]
            )
            for seat, evidence
            in self.stack_authority.items()
        }

    @property
    def participants(self):
        return self.frozen

    @property
    def is_frozen(self):
        return self.frozen is not None
