from collections import Counter


def plausible_values(result, minimum=0.0, maximum=500.0):
    """
    Extract only numerically plausible OCR candidates.

    This is perception validation, not poker semantics.
    """
    values = []

    if not isinstance(result, dict):
        return values

    for row in result.get("raw") or []:
        value = row.get("stack_bb")

        if value is None:
            continue

        value = float(value)

        if minimum <= value <= maximum:
            values.append(value)

    return values


def exact_candidate_support(result, value):
    value = float(value)

    return sum(
        1
        for item in plausible_values(result)
        if abs(item - value) < 0.001
    )


def select_stable_transition(
    readings,
    previous_value,
    max_drop_bb,
    min_support=3,
    min_consecutive=2,
):
    """
    Find the first stable downward stack transition.

    readings:
        [(frame_number, raw_reader_result), ...]

    Rules:
      * candidate must be <= previous accepted value;
      * drop must be <= max_drop_bb;
      * candidate needs min_support OCR variants;
      * same candidate must survive min_consecutive frames.

    No poker action is inferred here.
    """
    previous_value = float(previous_value)

    accepted = []

    for frame, result in readings:
        counts = Counter(
            plausible_values(result)
        )

        candidates = []

        for value, support in counts.items():
            if support < min_support:
                continue

            drop = previous_value - value

            if drop <= 0:
                continue

            if drop > float(max_drop_bb):
                continue

            candidates.append(
                (
                    support,
                    value,
                    drop,
                )
            )

        if not candidates:
            accepted.append(
                (
                    frame,
                    None,
                    None,
                )
            )
            continue

        candidates.sort(
            key=lambda item: (
                -item[0],
                item[1],
            )
        )

        support, value, drop = candidates[0]

        accepted.append(
            (
                frame,
                value,
                support,
            )
        )

    for index in range(
        0,
        len(accepted) - min_consecutive + 1,
    ):
        window = accepted[
            index:index + min_consecutive
        ]

        values = [
            item[1]
            for item in window
        ]

        if values[0] is None:
            continue

        if all(
            value == values[0]
            for value in values
        ):
            value = values[0]

            return {
                "frame": window[0][0],
                "value": value,
                "delta_bb": round(
                    previous_value - value,
                    2,
                ),
                "support": [
                    item[2]
                    for item in window
                ],
                "frames": [
                    item[0]
                    for item in window
                ],
            }

    return None


def candidate_values(*results):
    """
    Collect numeric stack candidates actually observed by independent
    perception families.

    No decimal insertion, digit substitution, or poker semantics.
    """
    values = []

    for result in results:
        if not isinstance(result, dict):
            continue

        direct = result.get("stack_bb")

        if direct is not None:
            values.append(float(direct))

        for row in result.get("raw") or []:
            value = row.get("stack_bb")

            if value is not None:
                values.append(float(value))

    return values


def select_continuity_candidate(
    previous_value,
    *results,
    max_drop_bb=None,
):
    """
    Select among values that perception actually observed.

    Rules:
      * stack may not increase;
      * candidate must be non-negative;
      * optional max_drop_bb bounds the transition;
      * nearest valid candidate to the previous trusted stack wins.

    This resolves perception ambiguity only. It does not infer an action.
    """
    previous = float(previous_value)

    candidates = sorted(
        set(
            candidate_values(*results)
        )
    )

    valid = []

    for value in candidates:
        if value < 0.0:
            continue

        delta = previous - value

        if delta < 0.0:
            continue

        if (
            max_drop_bb is not None
            and delta > float(max_drop_bb)
        ):
            continue

        valid.append(
            (
                delta,
                value,
            )
        )

    if not valid:
        return None

    valid.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    delta, value = valid[0]

    return {
        "previous_value": previous,
        "value": value,
        "delta_bb": round(delta, 2),
        "candidates": candidates,
    }
