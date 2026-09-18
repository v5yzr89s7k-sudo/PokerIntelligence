from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class FactoryComparison:
    passed: bool
    errors: Tuple[str, ...]


def _expected_action_tuple(item):
    return (
        item.street,
        item.seat,
        item.action,
        item.amount_bb,
        item.raise_to_bb,
    )


def compare_factory_run(
    scenario,
    run,
):
    errors = []

    expected_actions = tuple(
        _expected_action_tuple(item)
        for item in scenario.expected_actions
    )

    if run.final_actions != expected_actions:
        errors.append(
            "final semantic actions mismatch: "
            f"{run.final_actions}"
        )

    if len(run.publications) != len(
        scenario.expected_publications
    ):
        errors.append(
            "publication count mismatch: "
            f"observed={len(run.publications)} "
            f"expected="
            f"{len(scenario.expected_publications)}"
        )

    for index, expected in enumerate(
        scenario.expected_publications
    ):
        if index >= len(run.publications):
            break

        observed = run.publications[index]

        identity = (
            observed.frame,
            observed.street,
            observed.action_count,
            observed.next_actor,
        )

        target = (
            expected.frame,
            expected.street,
            expected.action_count,
            expected.next_actor,
        )

        if identity != target:
            errors.append(
                f"publication {index + 1} mismatch: "
                f"observed={identity} "
                f"expected={target}"
            )

        for token in expected.required_text:
            if token not in observed.text:
                errors.append(
                    f"publication {index + 1} "
                    f"missing text: {token}"
                )

        for token in expected.forbidden_text:
            if token in observed.text:
                errors.append(
                    f"publication {index + 1} "
                    f"contains forbidden text: {token}"
                )

        for marker, token in (
            expected.forbidden_text_after
        ):
            if marker not in observed.text:
                errors.append(
                    f"publication {index + 1} "
                    f"missing scoped marker: {marker}"
                )
                continue

            suffix = observed.text.split(
                marker,
                1,
            )[1]

            if token in suffix:
                errors.append(
                    f"publication {index + 1} "
                    f"contains forbidden text after "
                    f"{marker}: {token}"
                )

    return FactoryComparison(
        passed=not errors,
        errors=tuple(errors),
    )
