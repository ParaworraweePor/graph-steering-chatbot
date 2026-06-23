"""End-to-end async-turn-loop tests using the offline stub + echo generator.

Exercises:
  - async_turn returns {reply, technique, phase, extraction_mode, ...}
  - per-turn extraction (via StubExtractor "Label: text" lines) fills the graph
  - validate_phase refuses to advance until the V4_flat node-class minimums hold
  - reset clears the graph + history
"""

from __future__ import annotations

import asyncio

from cbt_kg.extract import StubExtractor
from cbt_kg.generate import EchoGenerator
from cbt_kg.graph_memory import InMemoryGraphStore
from cbt_kg.ontology import CBTSchema
from cbt_kg.therapy import Session, async_turn, turn, validate_phase


def _make_session() -> Session:
    schema = CBTSchema()
    return Session(
        schema=schema,
        graph=InMemoryGraphStore(schema),
        extractor=StubExtractor(),
        generator=EchoGenerator(),
    )


def test_async_turn_returns_expected_keys():
    session = _make_session()
    result = asyncio.run(async_turn(session, "Situation: exam tomorrow"))
    assert "reply" in result
    assert "phase" in result
    assert "technique" in result
    assert "extraction_mode" in result
    assert result["extraction_mode"] in ("sync", "async")


def test_stub_extractor_creates_nodes():
    session = _make_session()
    turn(session, "Situation: exam tomorrow\nAutomaticThought: I will fail")
    counts = session.graph.snapshot()["counts"]
    assert counts.get("Situation", 0) >= 1
    assert counts.get("AutomaticThought", 0) >= 1


def test_phase_gates_block_when_classes_missing():
    g = InMemoryGraphStore(CBTSchema())
    # No Problem yet — cannot advance to Exploration.
    assert validate_phase("Exploration", "Rapport", g, turn_count=5) == "Rapport"
    g.upsert_node("Problem", {"description": "work stress", "domain": "work"}, 1)
    # Problem present + 2 turns → Exploration allowed.
    assert validate_phase("Exploration", "Rapport", g, turn_count=2) == "Exploration"
    # Technique still blocked (no AT + Situation yet).
    assert validate_phase("Technique", "Exploration", g, turn_count=10) == "Exploration"
    # Add AT + Situation, advance.
    g.upsert_node("Situation", {"description": "exam"}, 3)
    g.upsert_node("AutomaticThought", {"content": "I will fail"}, 3)
    assert validate_phase("Technique", "Exploration", g, turn_count=5) == "Technique"


def test_phase_gates_block_consolidation_until_adaptive_response():
    g = InMemoryGraphStore(CBTSchema())
    g.upsert_node("Problem", {"description": "x", "domain": "work"}, 1)
    g.upsert_node("Situation", {"description": "y"}, 2)
    g.upsert_node("AutomaticThought", {"content": "z"}, 3)
    # ≥12 turns but no AdaptiveResponse → still Technique.
    assert validate_phase("Consolidation", "Technique", g, turn_count=12) == "Technique"
    g.upsert_node("AdaptiveResponse", {"content": "I can handle this"}, 13)
    assert validate_phase("Consolidation", "Technique", g, turn_count=12) == "Consolidation"


def test_validate_phase_allows_staying_or_going_back():
    g = InMemoryGraphStore(CBTSchema())
    assert validate_phase("Rapport", "Rapport", g, 0) == "Rapport"
    assert validate_phase("Rapport", "Technique", g, 0) == "Rapport"


def test_reset_clears_graph_and_history():
    session = _make_session()
    turn(session, "Situation: exam")
    assert session.graph.count_found("Situation") >= 1
    session.graph.reset()
    session.history.clear()
    session.transcript.clear()
    session.turn_count = 0
    assert session.graph.count_found("Situation") == 0


def test_extraction_lock_exists():
    session = _make_session()
    assert isinstance(session.extraction_lock, asyncio.Lock)
