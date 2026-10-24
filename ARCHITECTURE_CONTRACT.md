# POKER INTELLIGENCE — ARCHITECTURAL CONTRACT

Status: BINDING
Decision date: October 23, 2026

## PRIMARY ARCHITECTURE

PokerIntelligence is a FULL-TABLE,
FRAME-BY-FRAME PERCEPTION ENGINE.

Every captured frame must independently observe
the complete table:

- All player seats
- Hole-card presence and disappearance
- Stack values and physical stack changes
- Bet-region appearance and disappearance
- Player presence and identity
- Dealer-button position
- Board cards and street transitions
- Pot changes

## PROCESSING ORDER

1. Capture complete table.
2. Extract physical observations for every seat.
3. Compare against previous observations.
4. Correlate changes across frames.
5. Reconstruct chronological physical events.
6. HandEngine interprets poker semantics.
7. Publish current_hand.txt immediately.

## PROHIBITED ARCHITECTURE

- next_actor controlling which seats are observed
- next_actor gating physical evidence collection
- Retry ownership blocking full-table observation
- Reconstructing actions solely from turn order
- Adding exceptions to preserve obsolete architecture
- Multiple competing authorities for physical state

## NEXT_ACTOR

next_actor is derived semantic poker state.

It may validate action chronology.

It must never determine which physical
observations are collected.

## DEVELOPMENT RULES

Before modifying production code:

1. Read this contract.
2. Identify the architectural layer involved.
3. Verify the change preserves full-table observation.
4. Reject changes that violate this contract.
5. Validate repeated runs for determinism.

Preserve existing working components.

Do not rebuild the old architecture.

## SUCCESS CRITERIA

- Every seat observed independently
- Correct chronological action reconstruction
- No fabricated actions
- No permanently blocked action progression
- Immediate current_hand.txt publication
- Deterministic repeated validation
