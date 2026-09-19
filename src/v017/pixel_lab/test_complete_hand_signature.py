"""
V0.17 Pixel Lab complete-hand semantic signature.

The observer receives PNG pixels only.

This test reduces the complete observed hand to a stable canonical
signature suitable for repeated determinism comparison.

No ACR truth enters observer execution.
"""

import hashlib
import json

from src.v017.pixel_lab.test_real_acr_observer_pixels import (
    generator_phase,
    assert_wall,
    observer_phase,
)


def canonical_action(row):
    (
        sequence,
        street,
        seat,
        position,
        name,
        action,
        amount_bb,
        raise_to_bb,
    ) = row

    return {
        "sequence": sequence,
        "street": street,
        "seat": seat,
        "position": position,
        "name": name,
        "action": action,
        "amount_bb": amount_bb,
        "raise_to_bb": raise_to_bb,
    }


def build_signature():
    generator_phase()
    assert_wall()

    result = observer_phase()

    observer = result["observer"]

    terminal_returns = [
        {
            "frame": event.get("frame"),
            "seat": event.get("seat"),
            "prior": event.get("prior"),
            "resolved_value":
                event.get("resolved_value"),
            "amount_bb":
                event.get("amount_bb"),
        }
        for event in observer.events
        if (
            event.get("type")
            == "UNCALLED_RETURN_ADMITTED"
        )
    ]

    signature = {
        "actions": [
            canonical_action(row)
            for row in observer.hand.semantic_actions()
        ],
        "board": list(
            observer.hand.board
        ),
        "street":
            observer.hand.street,
        "next_actor":
            observer.hand.next_actor,
        "hand_complete":
            observer.hand.hand_complete,
        "completion_reason":
            observer.hand.completion_reason,
        "winner_seats":
            list(
                observer.hand.winner_seats
            ),
        "trusted_stacks": {
            seat: observer.trusted_stacks[
                seat
            ]
            for seat in sorted(
                observer.trusted_stacks
            )
        },
        "terminal_returns":
            terminal_returns,
        "pending_quantitative":
            list(
                observer
                .pending_quantitative_evidence
            ),
        "pending_card_disappearances":
            list(
                observer
                .pending_card_disappearances
            ),
    }

    return signature


def main():
    signature = build_signature()

    encoded = json.dumps(
        signature,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    print()
    print(
        "===== COMPLETE HAND SIGNATURE ====="
    )
    print(
        json.dumps(
            signature,
            indent=2,
            sort_keys=True,
        )
    )
    print()
    print(
        "sha256 =",
        digest,
    )

    assert len(
        signature["actions"]
    ) == 11

    assert signature["board"] == [
        "Jd",
        "9s",
        "Tc",
    ]

    assert (
        signature["hand_complete"]
        is True
    )

    assert (
        signature["completion_reason"]
        == "UNCONTESTED"
    )

    assert (
        signature["winner_seats"]
        == ["hero"]
    )

    assert (
        signature[
            "trusted_stacks"
        ]["hero"]
        == 97.16
    )

    assert signature[
        "terminal_returns"
    ] == [
        {
            "frame": 20,
            "seat": "hero",
            "prior": 95.04,
            "resolved_value": 97.16,
            "amount_bb": 2.12,
        }
    ]

    assert (
        signature[
            "pending_quantitative"
        ]
        == []
    )

    assert (
        signature[
            "pending_card_disappearances"
        ]
        == []
    )

    print()
    print(
        "11 BETTING ACTIONS: PASS"
    )
    print(
        "CANONICAL BOARD Jd 9s Tc: PASS"
    )
    print(
        "UNCONTESTED HERO RESULT: PASS"
    )
    print(
        "UNCALLED RETURN 2.12 BB: PASS"
    )
    print(
        "FINAL HERO STACK 97.16 BB: PASS"
    )
    print(
        "PENDING EVIDENCE EMPTY: PASS"
    )
    print()
    print(
        "V0.17 COMPLETE HAND SIGNATURE: PASS"
    )


if __name__ == "__main__":
    main()
