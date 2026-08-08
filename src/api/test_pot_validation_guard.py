def classify(expected, observed, pending=None, phase="PREFLOP"):
    tolerance = max(
        1.0,
        round(expected * 0.35, 2),
    )

    lower = expected - tolerance
    upper = expected + tolerance

    if observed < lower:
        return "reject", None

    if observed <= upper:
        return "accept", None

    pending = pending or {}

    confirmed = (
        pending.get("phase") == phase
        and pending.get("pot_bb") is not None
        and observed >= float(pending["pot_bb"]) - 1.0
    )

    if confirmed:
        return "accept_confirmed_high", None

    return "pending_high", {
        "phase": phase,
        "pot_bb": observed,
    }


# hand_0002 failure mode:
# one isolated high OCR spike must not become canonical.
decision, pending = classify(
    expected=18.5,
    observed=43.92,
)

assert decision == "pending_high"

decision, pending = classify(
    expected=18.5,
    observed=18.5,
    pending=pending,
)

assert decision == "accept"


# hand_0005 all-in progression:
# two high same-street readings establish a legitimate higher-pot regime.
decision, pending = classify(
    expected=2.5,
    observed=15.0,
)

assert decision == "pending_high"

decision, pending = classify(
    expected=2.5,
    observed=31.0,
    pending=pending,
)

assert decision == "accept_confirmed_high"


# A materially low observation remains invalid.
decision, _ = classify(
    expected=16.87,
    observed=4.38,
)

assert decision == "reject"

print("Temporal pot confirmation regression passed.")
