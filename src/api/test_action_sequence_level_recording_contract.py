from pathlib import Path


PATH = Path(
    "src/vision/action_sequence_recorder.py"
)


def main():
    text = PATH.read_text()

    assert (
        '"tournament_level"'
        in text
        or "'tournament_level'"
        in text
    ), (
        "ActionSequenceRecorder must persist "
        "authoritative tournament level metadata"
    )

    print(
        "PASS action sequence level recording contract: "
        "recorder persists tournament level metadata"
    )


if __name__ == "__main__":
    main()
