from dataclasses import dataclass
from difflib import unified_diff
from typing import List


@dataclass(frozen=True)
class ComparisonResult:
    passed: bool
    expected: str
    observed: str
    diff_lines: List[str]

    def format(self) -> str:
        if self.passed:
            return "PASS"

        lines = ["FAIL", ""]

        if self.diff_lines:
            lines.extend(self.diff_lines)
        else:
            lines.append("Expected and observed output differ.")

        return "\n".join(lines)


def normalize_output(text: str) -> str:
    """
    Normalize only inconsequential text-file differences.

    Do not normalize poker semantics, whitespace inside lines,
    ordering, numeric values, or wording.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = normalized.split("\n")

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def compare_output(
    expected: str,
    observed: str,
) -> ComparisonResult:
    expected_normalized = normalize_output(expected)
    observed_normalized = normalize_output(observed)

    passed = expected_normalized == observed_normalized

    if passed:
        return ComparisonResult(
            passed=True,
            expected=expected_normalized,
            observed=observed_normalized,
            diff_lines=[],
        )

    diff = list(
        unified_diff(
            expected_normalized.splitlines(),
            observed_normalized.splitlines(),
            fromfile="expected_current_hand.txt",
            tofile="generated_current_hand.txt",
            lineterm="",
        )
    )

    return ComparisonResult(
        passed=False,
        expected=expected_normalized,
        observed=observed_normalized,
        diff_lines=diff,
    )
