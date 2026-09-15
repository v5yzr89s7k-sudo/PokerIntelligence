from pathlib import Path
import ast


def main():
    path = Path("src/api/api_event_coordinator.py")
    source = path.read_text()
    tree = ast.parse(source)

    main_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "main"
    )

    offenders = []

    for node in ast.walk(main_fn):
        if not isinstance(node, ast.If):
            continue

        text = ast.get_source_segment(
            source,
            node.test,
        ) or ""

        normalized = "".join(
            text.split()
        )

        if normalized != "notuse_sck_capture":
            continue

        sleeps = []

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            fn = child.func

            if not (
                isinstance(fn, ast.Attribute)
                and isinstance(fn.value, ast.Name)
                and fn.value.id == "time"
                and fn.attr == "sleep"
            ):
                continue

            sleeps.append(
                ast.get_source_segment(
                    source,
                    child,
                )
            )

        if sleeps:
            offenders.append({
                "line": node.lineno,
                "condition": text,
                "sleeps": sleeps,
            })

    print(
        "legacy_or_replay_sleep_blocks:",
        offenders,
    )

    assert not offenders, (
        "RED: coordinator still adds legacy polling sleeps "
        "to replay frames even though PacedReplayCapture "
        "already owns replay timing: "
        + repr(offenders)
    )

    replay = Path(
        "src/api/paced_replay_capture.py"
    ).read_text()

    assert "time.sleep(remaining)" in replay, (
        "PacedReplayCapture no longer owns recorded pacing"
    )

    print(
        "PASS: replay has one pacing owner: "
        "PacedReplayCapture"
    )


if __name__ == "__main__":
    main()
