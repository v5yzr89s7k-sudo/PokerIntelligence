from src.state.street_commitment_tracker import StreetCommitmentTracker


tracker = StreetCommitmentTracker()

tracker.reset_street("PREFLOP")
state = tracker._state("PREFLOP")

assert state.street == "PREFLOP"

assert state.committed == set()
assert state.street_order == []
assert state.pending_to_act == []
assert state.needs_response_from == []
assert state.acted == set()

assert state.last_aggressor is None
assert state.current_price == 0.0
assert state.betting_open is False


state.street_order.extend([
    "UTG",
    "HJ",
    "CO",
])

state.pending_to_act.extend([
    "UTG",
    "HJ",
])

state.needs_response_from.extend([
    "HJ",
    "CO",
])

state.acted.add("CO")
state.last_aggressor = "BTN"
state.current_price = 2.5
state.betting_open = True


serialized = tracker.to_dict()

assert serialized["PREFLOP"]["committed"] == []

assert serialized["PREFLOP"]["street_order"] == [
    "UTG",
    "HJ",
    "CO",
]

assert serialized["PREFLOP"]["pending_to_act"] == [
    "UTG",
    "HJ",
]

assert serialized["PREFLOP"]["needs_response_from"] == [
    "HJ",
    "CO",
]

assert serialized["PREFLOP"]["acted"] == [
    "CO",
]

assert serialized["PREFLOP"]["last_aggressor"] == "BTN"
assert serialized["PREFLOP"]["current_price"] == 2.5
assert serialized["PREFLOP"]["betting_open"] is True


tracker.reset_street("PREFLOP")
state = tracker._state("PREFLOP")

assert state.committed == set()
assert state.street_order == []
assert state.pending_to_act == []
assert state.needs_response_from == []
assert state.acted == set()

assert state.last_aggressor is None
assert state.current_price == 0.0
assert state.betting_open is False

print("StreetCommitmentState regression tests passed.")
