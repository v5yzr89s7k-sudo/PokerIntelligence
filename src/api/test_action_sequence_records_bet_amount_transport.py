"""
Action-sequence quantitative replay recording contract.

Bet-amount requests/results are asynchronous transport and must not be
copied from ActionSequenceRecorder.record(), which is on the coordinator
frame path.

Correct ownership:

    recorder starts session
        ->
    session destination becomes visible across processes
        ->
    runner stops coordinator and asynchronous workers
        ->
    runner snapshots stable bet request/result transport into that
    action-sequence session

This preserves original quantitative API perception for deterministic
future replay without adding recurring file-copy work to frame capture.
"""

from pathlib import Path
import ast


RECORDER_PATH = Path(
    "src/vision/action_sequence_recorder.py"
)

RUNNER_PATH = Path(
    "src/api/run_live_observer.py"
)


def function(tree, name):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return node

    return None


def source_segment(source, node):
    if node is None:
        return ""

    return ast.get_source_segment(
        source,
        node,
    ) or ""


def main():
    recorder_source = RECORDER_PATH.read_text()
    runner_source = RUNNER_PATH.read_text()

    recorder_tree = ast.parse(
        recorder_source
    )

    runner_tree = ast.parse(
        runner_source
    )

    start_session = function(
        recorder_tree,
        "start_session",
    )

    record = function(
        recorder_tree,
        "record",
    )

    stop_all = function(
        runner_tree,
        "stop_all",
    )

    assert start_session is not None
    assert record is not None
    assert stop_all is not None

    start_source = source_segment(
        recorder_source,
        start_session,
    )

    record_source = source_segment(
        recorder_source,
        record,
    )

    shutdown_source = source_segment(
        runner_source,
        stop_all,
    )

    # ---------------------------------------------------------
    # CONTRACT 1:
    # recorder must publish/share the active session destination
    # so the parent runner can finalize transport after workers stop.
    # ---------------------------------------------------------

    pointer_markers = (
        "action_sequence_session",
        "session_pointer",
        "session_manifest",
        "active_session",
    )

    assert any(
        marker in start_source
        for marker in pointer_markers
    ), (
        "RED: ActionSequenceRecorder.start_session() does not "
        "publish the active session destination for cold-path "
        "runner finalization"
    )

    # ---------------------------------------------------------
    # CONTRACT 2:
    # never copy growing asynchronous transport from record().
    # ---------------------------------------------------------

    assert (
        "bet_amount_requests.jsonl"
        not in record_source
    ), (
        "recorder hot path must not copy "
        "bet_amount_requests.jsonl"
    )

    assert (
        "bet_amount_results.jsonl"
        not in record_source
    ), (
        "recorder hot path must not copy "
        "bet_amount_results.jsonl"
    )

    # ---------------------------------------------------------
    # CONTRACT 3:
    # runner shutdown owns the stable snapshot.
    # ---------------------------------------------------------

    assert (
        "bet_amount_requests.jsonl"
        in shutdown_source
    ), (
        "RED: runner cold shutdown does not preserve "
        "bet_amount_requests.jsonl into the action-sequence session"
    )

    assert (
        "bet_amount_results.jsonl"
        in shutdown_source
    ), (
        "RED: runner cold shutdown does not preserve "
        "bet_amount_results.jsonl into the action-sequence session"
    )

    # ---------------------------------------------------------
    # CONTRACT 4:
    # snapshot must happen only after bet worker termination.
    # ---------------------------------------------------------

    bet_stop = shutdown_source.find(
        'terminate_process("bet_amount_worker")'
    )

    request_copy = shutdown_source.find(
        "bet_amount_requests.jsonl"
    )

    result_copy = shutdown_source.find(
        "bet_amount_results.jsonl"
    )

    assert bet_stop >= 0

    assert (
        request_copy > bet_stop
        and result_copy > bet_stop
    ), (
        "RED: recorded bet transport is snapshotted before "
        "bet_amount_worker has stopped"
    )

    print(
        "PASS action-sequence bet transport recording contract: "
        "active session is shared across processes and stable "
        "bet transport is preserved only on the runner cold path"
    )


if __name__ == "__main__":
    main()
