"""
Response-to-aggression is continuity-search evidence only.

This contract deliberately avoids asserting source formatting.

Required architecture:
1. candidate ownership can retain response_to_aggression;
2. both continuity-window calculations recognize it;
3. final validate_stack_transition() commitment authorization does NOT
   use response_to_aggression.
"""

from pathlib import Path
import ast


PATH = Path(
    "src/api/api_event_coordinator.py"
)


def function_source(name):
    text = PATH.read_text()
    lines = text.splitlines()
    tree = ast.parse(text)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return "\n".join(
                lines[
                    node.lineno - 1:
                    node.end_lineno
                ]
            )

    raise AssertionError(
        f"{name}() not found"
    )


def main():
    source = PATH.read_text()

    # Candidate ownership captures contemporaneous response context.
    assert (
        'sources.add("response_to_aggression")'
        in source
    )

    # It must participate in both continuity-window decisions.
    assert source.count(
        '"response_to_aggression"'
    ) >= 3

    enrichment = function_source(
        "enrich_stack_change_measurements"
    )

    # Final semantic validation must still exist.
    assert (
        "validate_stack_transition("
        in enrichment
    )

    # Inspect only the region immediately surrounding the final
    # semantic validator call.
    validator_index = enrichment.rfind(
        "validate_stack_transition("
    )

    validator_region = enrichment[
        max(
            0,
            validator_index - 900,
        ):
        validator_index + 900
    ]

    print(
        "===== FINAL VALIDATOR REGION ====="
    )
    print(validator_region)

    # Response context may widen candidate search, but must never be
    # passed into or used to authorize the final semantic transition.
    assert (
        "response_to_aggression"
        not in validator_region
    ), (
        "REGRESSION: response-to-aggression leaked into "
        "final semantic stack authorization"
    )

    assert (
        "has_commitment_evidence"
        in validator_region
    ), (
        "final semantic commitment gate missing"
    )

    print()
    print(
        "PASS: response-to-aggression participates in "
        "continuity search but does not authorize final "
        "semantic stack validation"
    )


if __name__ == "__main__":
    main()
