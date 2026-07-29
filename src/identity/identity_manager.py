from src.identity.identity_record import IdentityRecord


class IdentityManager:
    """
    Single ownership boundary for player identity.

    This initial version is deliberately behavior-neutral. It establishes
    the interface that existing snapshot identity logic will migrate behind
    incrementally in later commits.
    """

    HERO_SOURCE = "hero_session"
    CACHE_SOURCE = "cache"
    UNRESOLVED_SOURCE = "unresolved"

    def resolve_hero(self, *, seat, cached_entry=None):
        """
        Resolve Hero from session-stable cached identity.

        Hero's visible nameplate may be replaced by transient action labels,
        so Hero identity must not depend on per-frame fingerprint matching.
        """
        entry = dict(cached_entry or {})

        return IdentityRecord(
            seat=seat,
            name=entry.get("name") or "",
            source=(
                self.HERO_SOURCE
                if entry.get("name")
                else self.UNRESOLVED_SOURCE
            ),
            confidence=(
                1.0
                if entry.get("name")
                else None
            ),
            changed=False,
        )

    def resolve_cached_opponent(self, *, seat, cached_entry=None):
        """
        Convert an already validated cache entry into an identity record.

        Fingerprint validation remains in the existing snapshot reader during
        this extraction phase. Moving that decision behind this interface is
        a later behavior-preserving commit.
        """
        entry = dict(cached_entry or {})

        return IdentityRecord(
            seat=seat,
            name=entry.get("name") or "",
            source=(
                self.CACHE_SOURCE
                if entry.get("name")
                else self.UNRESOLVED_SOURCE
            ),
            confidence=entry.get("confidence"),
            changed=False,
        )

    def unresolved(self, *, seat):
        return IdentityRecord(
            seat=seat,
            name="",
            source=self.UNRESOLVED_SOURCE,
            confidence=None,
            changed=False,
        )
