from src.v017 import run_live_observer as live


def main():
    assert callable(
        live.read_player_identities_v2
    )

    enricher = live.TemporalIdentityEnricher()

    try:
        assert (
            enricher.reader
            is live.read_player_identities_v2
        )
    finally:
        enricher.close()

    print(
        "TEMPORAL IDENTITY READER IMPORT CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
