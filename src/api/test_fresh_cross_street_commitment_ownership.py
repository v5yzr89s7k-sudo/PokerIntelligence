from types import SimpleNamespace

import src.api.api_event_coordinator as c


SEAT = "seat_top"


def changes_with_fresh_flop_bet():
    return SimpleNamespace(
        stack_change_details={},
        bet_region_transitions={
            SEAT: {
                "appeared": True,
            },
        },
        bet_region_appeared=[
            SEAT,
        ],
        occupied_bet_regions=[
            SEAT,
        ],
    )


def main():
    print("=" * 78)
    print(
        "FRESH FLOP COMMITMENT MUST NOT "
        "INHERIT PREFLOP OWING"
    )
    print("=" * 78)

    state = {
        "phase": "PREFLOP",
        "pending_stack_reads": {},
        "bet_region_street_owners": {},
    }

    changes = changes_with_fresh_flop_bet()

    # Reproduce the live boundary condition:
    #
    # canonical phase is still PREFLOP,
    # physical board/event street is already FLOP,
    # seat_top is still present in old-street owing,
    # BUT there is no pre-existing physical candidate
    # or bet-region owner for seat_top.
    street = c.commitment_evidence_street(
        state,
        changes,
        SEAT,
        "FLOP",
        old_street_owing_seats={
            SEAT,
        },
    )

    print()
    print("canonical phase: PREFLOP")
    print("physical street: FLOP")
    print("existing candidate: none")
    print("existing bet owner: none")
    print(
        "old-street owing:",
        {SEAT},
    )
    print("resolved street:", street)

    assert street == "FLOP", (
        "BUG: fresh FLOP commitment inherited "
        "PREFLOP solely from old-street owing "
        "despite having no old physical owner"
    )

    print()
    print(
        "PASS: fresh next-street physical "
        "commitment owns FLOP"
    )


if __name__ == "__main__":
    main()
