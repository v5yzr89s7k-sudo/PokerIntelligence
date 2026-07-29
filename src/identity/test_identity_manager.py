from src.identity.identity_manager import IdentityManager
from src.identity.identity_record import IdentityRecord


def test_identity_record():
    record = IdentityRecord(
        seat="seat_top",
        name="PlayerOne",
        source="cache",
        confidence=0.98,
    )

    assert record.resolved is True
    assert record.to_dict() == {
        "seat": "seat_top",
        "name": "PlayerOne",
        "source": "cache",
        "confidence": 0.98,
        "changed": False,
        "resolved": True,
    }


def test_hero_session_identity():
    manager = IdentityManager()

    record = manager.resolve_hero(
        seat="hero",
        cached_entry={
            "name": "poker5068",
        },
    )

    assert record.name == "poker5068"
    assert record.source == "hero_session"
    assert record.confidence == 1.0
    assert record.resolved is True


def test_unresolved_hero():
    manager = IdentityManager()

    record = manager.resolve_hero(
        seat="hero",
        cached_entry=None,
    )

    assert record.name == ""
    assert record.source == "unresolved"
    assert record.resolved is False


def test_cached_opponent():
    manager = IdentityManager()

    record = manager.resolve_cached_opponent(
        seat="seat_upper_right",
        cached_entry={
            "name": "OpponentOne",
            "confidence": 0.91,
        },
    )

    assert record.name == "OpponentOne"
    assert record.source == "cache"
    assert record.confidence == 0.91


def main():
    test_identity_record()
    test_hero_session_identity()
    test_unresolved_hero()
    test_cached_opponent()

    print("identity engine scaffold tests passed")


if __name__ == "__main__":
    main()
