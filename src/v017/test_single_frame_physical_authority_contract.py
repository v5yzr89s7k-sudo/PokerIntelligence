from pathlib import Path


def main():
    live = Path(
        "src/v017/run_live_observer.py"
    ).read_text()

    snapshot = Path(
        "src/api/table_snapshot_reader_core_v2.py"
    ).read_text()

    # Live transaction owns exactly one acquired native frame.
    start = live.index("def run_hand(")
    end = live.index("\ndef main(", start)
    run_hand = live[start:end]

    assert "image, frame_path = (" in run_hand
    assert "capture_image(window)" in run_hand

    # The semantic transaction itself must never recapture.
    start = live.index("def process_frame_transaction(")
    end = live.index("\ndef run_hand(", start)
    transaction = live[start:end]

    assert "capture_image(" not in transaction

    # Snapshot may still observe dealer metadata, but it is not
    # authoritative for topology or position assignment.
    assert "detect_native_dealer(" in live
    assert "detect_dealer_button(" in snapshot

    start = live.index("def build_observer_from_frame(")
    end = live.index("\ndef bootstrap_observer(", start)
    bootstrap = live[start:end]

    assert "confirmed_dealer_seat=None" in bootstrap
    assert "[SNAPSHOT_DEALER_IGNORED]" in bootstrap

    position_index = bootstrap.index(
        "positions = assign_positions("
    )

    authority_region = bootstrap[
        max(0, position_index - 600):
        position_index + 400
    ]

    assert "confirmed_dealer_seat" in authority_region
    assert "dealer_seat," in authority_region

    print(
        "SINGLE LIVE FRAME TRANSACTION: CONFIRMED"
    )
    print(
        "PHYSICAL DEALER OWNS POSITION AUTHORITY: CONFIRMED"
    )
    print(
        "SNAPSHOT DEALER IS NON-AUTHORITATIVE: CONFIRMED"
    )


if __name__ == "__main__":
    main()
