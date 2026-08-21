from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[2]

RUN_SUITE = ROOT / "src/validation/run_suite.py"
GOLDEN_HAND = ROOT / "src/validation/golden_hand.py"
EVENT_REPLAY = ROOT / "src/validation/event_replay.py"
RECORDER = ROOT / "src/validation/record_golden_hand.py"


def parse(path):
    return ast.parse(path.read_text())


def string_literals(path):
    values = set()

    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.add(node.value)

    return values


def main():
    print("===== CURRENT FORMAT OWNERSHIP =====")

    recorder_text = RECORDER.read_text()

    assert '"format_version": 2' in recorder_text, (
        "golden recorder must persist current format_version=2"
    )

    print("PASS: recorder persists current format_version=2")

    print()
    print("===== GENERALIZED VERSION-GATE CONTRACT =====")

    combined = "\n".join(
        path.read_text()
        for path in (
            RUN_SUITE,
            GOLDEN_HAND,
            EVENT_REPLAY,
        )
    )

    has_version_read = "format_version" in combined

    compatibility_terms = (
        "legacy",
        "compatible",
        "compatibility",
        "unsupported",
        "schema",
    )

    has_compatibility_policy = (
        has_version_read
        and any(
            term in combined.lower()
            for term in compatibility_terms
        )
    )

    print("validator reads format_version:", has_version_read)
    print(
        "validator has compatibility policy:",
        has_compatibility_policy,
    )

    assert has_version_read, (
        "REPRODUCED: golden metadata has format_version, "
        "but validation does not consume it"
    )

    assert has_compatibility_policy, (
        "REPRODUCED: validator has no generalized "
        "golden-format compatibility policy"
    )

    print(
        "PASS: validator owns an explicit generalized "
        "golden-format compatibility gate"
    )


if __name__ == "__main__":
    main()
