from pathlib import Path


def test_coordinator_defers_empty_participant_context():
    source = Path(
        "src/api/api_event_coordinator.py"
    ).read_text()

    guard = """        if frozen_participants:
            emit({
                "type": "table_context",
"""

    defer_log = """                "[TABLE_CONTEXT_DEFER] "
"""

    hero_emit = """        emit({
            "type": "hero_cards",
"""

    assert guard in source
    assert defer_log in source
    assert hero_emit in source

    assert source.index(guard) < source.index(hero_emit)
    assert source.index(defer_log) < source.index(hero_emit)
