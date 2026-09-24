from pathlib import Path


SOURCE = Path(
    "src/v017/run_live_observer.py"
).read_text()


def main():
    production_sleep = '''        if transaction.outcome != "CONTINUE":
            return

        time.sleep(
            FRAME_INTERVAL_SECONDS
        )
'''

    count = SOURCE.count(
        production_sleep
    )

    print(
        "production_post_transaction_sleep_count =",
        count,
    )

    # Current production is expected to fail this contract.
    assert count == 0, (
        "live acquisition loop still imposes "
        "FRAME_INTERVAL_SECONDS after every "
        "CONTINUE transaction"
    )

    print(
        "NO ARTIFICIAL POST-TRANSACTION DELAY: PASS"
    )


if __name__ == "__main__":
    main()
