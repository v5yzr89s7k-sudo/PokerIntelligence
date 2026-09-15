# Poker Intelligence Runtime Architecture and Ownership

## Status

Structural audit performed September 4, 2026.

Current production checkpoint before cleanup:

    a3129c9
    v0.15.11 stabilize physical action chronology and call accounting

The purpose of this document is to define the authoritative runtime
architecture and prevent multiple subsystems from independently owning
the same poker fact.

---

# Primary Product

The product is:

    runtime/live/current_hand.txt

It is a presentation of the canonical hand.

Presentation must never become an independent source of poker truth.

---

# Effective Live Runtime

`src/api/run_live_observer.py` launches:

    api_event_state_machine.py
    api_snapshot_worker.py
    api_hero_worker.py
    api_board_worker.py
    api_pot_worker.py
    api_bet_amount_worker.py
    api_stack_worker.py
    api_boundary_stack_worker.py
    api_event_coordinator.py

Other historical or alternate modules are not part of the effective
live runtime unless explicitly proven otherwise.

---

# Canonical Architecture

    SCK / Replay Frame Source
                |
                v
        Local Perception
                |
                v
           Coordinator
                |
                | evidence events
                v
           Event Stream
                |
                v
          State Machine
                |
                v
          CanonicalHand
                |
                v
        CanonicalHandStore
                |
                v
             Renderer
                |
                v
      runtime/live/current_hand.txt

Live and replay must share the same path from local perception/evidence
forward.

They may differ only in frame source and pacing.

---

# Ownership Rule

Every semantic fact has exactly one authoritative owner.

Other copies may exist only as:

1. raw evidence;
2. transport state;
3. retry state;
4. derived/read-only presentation;
5. diagnostic state.

A derived or transport copy must never overwrite its authoritative
source independently.

---

# Layer 1 — Frame Source

## Live

ScreenCaptureKit supplies the current in-memory table image.

## Replay

Recorded immutable frames supply the image.

## Ownership

Frame source owns pixels and capture timing only.

It owns no poker semantics.

---

# Layer 2 — Local Perception

Primary component:

    src/events/local_event_detector.py

Responsibilities include visual evidence such as:

    board count
    hero-card visibility
    stack motion
    bet-region occupancy/transitions
    opponent-card disappearance
    action-button state
    dealer evidence
    UI activity

## Ownership

Local perception owns measurements/evidence only.

It must not decide canonical poker actions.

---

# Layer 3 — Coordinator

Primary component:

    src/api/api_event_coordinator.py

Current responsibilities include:

    capture orchestration
    frame ownership/materialization
    participant evidence
    worker request transport
    worker result collection
    stack candidate lifecycle
    startup stack recovery
    fast actor evidence
    physical actor evidence
    Hero coordination
    Board coordination
    Pot coordination
    bet-amount coordination
    boundary-stack coordination
    replay synchronization
    action-episode coordination
    inference event publication
    winner evidence
    hand-completion evidence

## Allowed authoritative state

Coordinator may authoritatively own only perception/transport state:

    worker request ownership
    worker cursors
    frame ownership
    retry timers
    detector baselines
    evidence candidate lifecycle
    replay pacing/cursors

## Forbidden authoritative state

Coordinator must not independently own canonical:

    current street
    players-to-act
    betting price
    aggressor
    player stacks
    player folded state
    canonical actions
    pot
    board identity
    final hand result

Temporary copies may exist only to route evidence and must be derived
from canonical state.

---

# Layer 4 — Workers

Active workers:

    api_snapshot_worker.py
    api_hero_worker.py
    api_board_worker.py
    api_pot_worker.py
    api_bet_amount_worker.py
    api_stack_worker.py
    api_boundary_stack_worker.py

## Ownership

Workers own no poker state.

Workers transform immutable frame evidence into result evidence.

Every request must own the exact immutable frame used by the worker.

Worker output is evidence, not canonical truth.

---

# Layer 5 — Event Stream

Primary transport:

    runtime/live/api_events.jsonl

Events communicate evidence and lifecycle requests between the
coordinator/workers and state machine.

Events are immutable historical facts.

Events do not themselves constitute canonical state.

---

# Layer 6 — State Machine

Primary component:

    src/api/api_event_state_machine.py

Responsibilities:

    consume events in order
    validate lifecycle
    reconcile delayed evidence
    invoke semantic resolvers
    preserve unresolved evidence
    reject stale/cross-hand evidence
    apply accepted semantic changes to CanonicalHand

## Allowed authoritative state

State-machine-local state may own:

    event cursors
    deferred event buffers
    pending evidence
    reconciliation bookkeeping
    hand-token validation context

It must not become an independent poker model.

---

# Layer 7 — CanonicalHand

Primary component:

    src/state/canonical_hand.py

CanonicalHand is the authoritative poker model.

It owns:

    hand identity
    player roster
    poker positions
    starting stacks
    current stacks
    last confirmed stacks
    folded status
    current street
    board
    actions
    commitments
    players-to-act
    current betting price
    last aggressor
    pot
    showdown
    result
    hand completion

Semantic resolvers and trackers may mutate these facts only through
defined canonical operations.

There must not be a second independently authoritative copy.

---

# Stack Ownership Contract

Correct chain:

    visual stack evidence
        ->
    immutable worker frame
        ->
    stack worker result
        ->
    coordinator evidence event
        ->
    state-machine validation
        ->
    CanonicalHand player stack

Authoritative fields:

    PlayerState.starting_stack_bb
    PlayerState.current_stack_bb
    PlayerState.last_confirmed_stack_bb

The following are NOT authoritative poker stacks:

    starting_stack_cache
    pending_startup_stack_seats
    pending_stack_reads
    pending_stack_worker_requests
    ActionEpisodeManager.pending_stack_by_seat

They are transport/retry/evidence state only.

---

# Action Ownership Contract

Correct chain:

    physical visual evidence
        ->
    actor/action evidence
        ->
    state-machine semantic reconciliation
        ->
    canonical betting/action state
        ->
    CanonicalHand action

No downstream action may be fabricated solely because a later actor was
observed unless the semantic resolver has sufficient evidence under the
defined chronology contract.

---

# Street Ownership Contract

CanonicalHand.current_street is the authoritative poker street.

Other street/phase values must be either:

    evidence-time street labels
    transport routing values
    state-machine lifecycle bookkeeping
    presentation derived from CanonicalHand

They must not independently advance canonical poker state.

This is a known cleanup area.

---

# Presentation Ownership Contract

Presentation modules may read canonical state and render:

    current_hand.txt
    live status
    history files

Presentation must not independently own:

    players
    positions
    dealer
    current street
    stacks
    actions
    board
    pot

Any presentation cache must be derived and replaceable.

---

# Known Structural Risks Found by Audit

## Coordinator size

`api_event_coordinator.py` is approximately 9,950 lines.

Its `main()` is approximately 1,767 lines.

`enrich_stack_change_measurements()` is approximately 1,755 lines.

This module currently crosses too many ownership boundaries.

Do not mechanically split it until semantic ownership is corrected.

## State machine size

`api_event_state_machine.py` is approximately 6,148 lines.

It contains extensive reconciliation and preservation logic in addition
to canonical mutation.

## Duplicate street/phase representations

Street or phase currently appears in:

    coordinator state
    state-machine state
    CanonicalHand
    live presentation state
    StreetActionTracker
    BettingRoundTracker / StreetCommitmentTracker context

These must be classified as authoritative versus derived.

## Stack staging layers

Stack information currently exists in:

    worker transport
    startup cache
    pending stack reads
    stack candidates
    action episodes
    state-machine pending baseline/update buffers
    CanonicalHand

Only CanonicalHand may own accepted poker stack state.

---

# Confirmed Historical / Inactive Paths

Not launched by the current live runner:

    src/api/api_snapshot_worker_v2.py
    src/live_state_machine.py
    src/api/api_event_to_live_writer.py
    src/live/live_hand_cycle_writer.py

`src/live_state_machine.py` is referenced by the older
`src/capture_loop.py` architecture.

These files are candidates for later archival/removal only after import
and tooling dependencies are verified.

---

# Confirmed Superseded Function

In `api_event_coordinator.py`:

    retry_one_startup_stack()

is the old synchronous startup-stack recovery implementation.

The current live path uses:

    queue_one_startup_stack_async()
    consume_startup_stack_worker_results()

The synchronous function is a removal candidate after the async path
passes the required validation gate.

---

# Structural Cleanup Sequence

## Phase 1

Inventory and remove proven dead/superseded production paths.

No semantic behavior changes.

## Phase 2

Enforce ownership contracts with assertions/tests.

CanonicalHand becomes the only poker-state authority.

## Phase 3

Remove duplicate street/phase authority.

## Phase 4

Consolidate stack ownership.

## Phase 5

Consolidate action chronology and betting-round ownership.

## Phase 6

Make presentation a read-only canonical projection.

## Phase 7

Decompose coordinator and state machine along the established ownership
boundaries.

File movement is deliberately last. Ownership must be corrected before
physical decomposition.

---

# Validation Discipline

No structural milestone is accepted from one successful replay.

After every meaningful change:

1. run focused regression tests;
2. run the July 22 visual ground-truth replay;
3. repeat the same true-paced replay at least three times;
4. compare canonical semantic outputs;
5. require deterministic equivalence;
6. validate on fresh live ACR hands;
7. only then commit the milestone.

The live product remains:

    runtime/live/current_hand.txt
