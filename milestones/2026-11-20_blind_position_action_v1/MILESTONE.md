# PokerIntelligence — Protected Engineering Milestone

Date: November 20, 2026

Production Swift SHA-256:
700101d94a136375810700eefea35c0c65b7c01f8e77199cdc812ef853e4ea2a

BoardPresence SHA-256:
8a363f2c9a88b81c68316e3770e79168e624bf0d5ca9080d2637af1d6c3d24cf

Verified on the user's Mac:
- Native self-test and parallel self-test: PASS
- Rapid-action episodes, frames 22, 166, 173: PASS
- Durable checkpoint and restart recovery: PASS
- Three blind-based dealer assignments: PASS
- Stable seven-seat ring and nameplate-dropout guard: PASS
- Three relative seat-order candidates: PASS
- Positional determinism: 3/3
- Unverified actions promoted: 0
- API calls: 0

The previous version fb8d8130... passed a complete 355-frame
replay preserving 26 actions, 7 streets, 2 winner observations,
and 3 unordered episodes. That complete replay has NOT yet
been rerun on this exact 700101d9... version.

NON-REGRESSION REQUIREMENTS:
1. Preserve blind-derived dealer, SB, BB and seating ring.
2. Preserve full-table action recognition and rapid episodes.
3. Preselected Fold is not an executed Fold.
4. Never invent action chronology or exact wager amounts.
5. Preserve the single authoritative Recorder.
6. Preserve physical evidence, frame IDs and fingerprints.
7. Preserve recovery, idempotency and prior accepted events.
8. Run milestone regression tests before replacing source.

This snapshot is a rollback baseline, not certification of
complete hand-history accuracy.
