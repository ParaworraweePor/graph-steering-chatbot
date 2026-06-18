"""Proves the turn loop works with zero external services: InMemoryGraphStore
+ StubExtractor + EchoGenerator."""

from extract import StubExtractor
from generate import EchoGenerator
from graph import InMemoryGraphStore
from orchestrator import Session, turn
from schema import PlaceboSchema

ALL_FIELDS = ["name", "emotion", "placeholder_a", "placeholder_b", "placeholder_c"]


def _make_session() -> Session:
    schema = PlaceboSchema()
    return Session(
        schema=schema,
        graph=InMemoryGraphStore(schema),
        extractor=StubExtractor(),
        generator=EchoGenerator(),
    )


def test_turn_fills_graph_and_shrinks_missing():
    session = _make_session()

    missing_before = session.graph.missing()
    assert missing_before == ALL_FIELDS

    result1 = turn(session, "name: Alex")
    assert result1["deltas"] == {"name": "Alex"}
    assert result1["slots"]["name"]["acquired"] is True
    assert result1["slots"]["name"]["value"] == "Alex"

    missing_after_1 = session.graph.missing()
    assert missing_after_1 == ALL_FIELDS[1:]
    assert len(missing_after_1) < len(missing_before)

    result2 = turn(session, "emotion: curious")
    missing_after_2 = session.graph.missing()
    assert missing_after_2 == ALL_FIELDS[2:]
    assert len(missing_after_2) < len(missing_after_1)

    result3 = turn(session, "placeholder_a: hello there")
    result4 = turn(session, "placeholder_b: second value")
    result5 = turn(session, "placeholder_c: third value")
    assert session.graph.missing() == []
    assert "placeholder_c=third value" in session.graph.acquired_summary()

    for result in (result1, result2, result3, result4, result5):
        assert isinstance(result["reply"], str) and result["reply"]


def test_turn_ignores_unknown_fields():
    session = _make_session()
    result = turn(session, "unknown_field: some value")
    assert result["deltas"] == {}
    assert session.graph.missing() == ALL_FIELDS


def test_reset_clears_acquired_fields():
    session = _make_session()
    turn(session, "name: Alex")
    assert session.graph.missing() == ALL_FIELDS[1:]

    session.graph.reset()
    assert session.graph.missing() == ALL_FIELDS
