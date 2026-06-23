"""Tests for the deterministic query executor + readers."""

from __future__ import annotations

import json
from pathlib import Path

from cbt_kg.graph_memory import InMemoryGraphStore
from cbt_kg.graph_reader import JsonGraphReader, LiveGraphReader
from cbt_kg.ontology import CBTSchema
from cbt_kg.query import execute


def _seeded_graph() -> InMemoryGraphStore:
    g = InMemoryGraphStore(CBTSchema())
    g.upsert_node("Problem", {"description": "exam anxiety", "domain": "academic"}, 1)
    sit = g.upsert_node("Situation", {"description": "exam tomorrow",
                                       "kind": "externalSituation"}, 1)
    at = g.upsert_node("AutomaticThought",
                       {"content": "I will fail", "modality": "verbal",
                        "distortionType": "catastrophizing"}, 1)
    re = g.upsert_node("Reaction", {"content": "anxious", "channel": "emotional",
                                     "valence": "negative"}, 1)
    g.add_edge(sit.node_id, "triggers", at.node_id, evidence=[1])
    g.add_edge(at.node_id, "leadsTo", re.node_id,
               props={"reportedIntensity": "8/10"}, evidence=[1])
    return g


def test_live_reader_emits_canonical_nodes_and_edges():
    g = _seeded_graph()
    nodes, edges = LiveGraphReader(g).load()
    labels = {n.label for n in nodes}
    assert "Situation" in labels
    assert "AutomaticThought" in labels
    preds = {e.predicate for e in edges}
    assert "triggers" in preds
    assert "leadsTo" in preds


def test_execute_count_intent():
    g = _seeded_graph()
    nodes, edges = LiveGraphReader(g).load()
    rs = execute({"intent": "count", "node_labels": ["AutomaticThought"]},
                 nodes, edges)
    assert rs["counts"]["AutomaticThought"] == 1


def test_execute_list_intent_with_property_filter():
    g = _seeded_graph()
    nodes, edges = LiveGraphReader(g).load()
    rs = execute({
        "intent": "list",
        "node_labels": ["AutomaticThought"],
        "property_filters": {"distortionType": "catastrophizing"},
    }, nodes, edges)
    assert rs["intent"] == "list"
    assert len(rs["nodes"]) == 1
    assert rs["nodes"][0]["text"] == "I will fail"


def test_execute_trace_intent_walks_chain():
    g = _seeded_graph()
    nodes, edges = LiveGraphReader(g).load()
    rs = execute({
        "intent": "trace",
        "node_labels": ["Situation"],
        "predicates": ["triggers", "leadsTo"],
    }, nodes, edges)
    labels_walked = {n["label"] for n in rs["nodes"]}
    assert "Situation" in labels_walked
    assert "AutomaticThought" in labels_walked
    assert "Reaction" in labels_walked


def test_execute_summarize_intent():
    g = _seeded_graph()
    nodes, edges = LiveGraphReader(g).load()
    rs = execute({"intent": "summarize"}, nodes, edges)
    assert rs["counts"]["Situation"] >= 1
    assert rs["counts"]["AutomaticThought"] >= 1


def test_json_reader_round_trip(tmp_path: Path):
    """Hand-built V4_flat Stage-5-shaped JSON loads correctly."""
    payload = {
        "meta": {"schema_version": "ontology_v4_flat"},
        "tbox_nodes": [], "tbox_edges": [],
        "nodes": [
            {"id": "client_1", "label": "Client", "parent": None,
             "properties": {}, "evidence": []},
            {"id": "session_1", "label": "Session", "parent": None,
             "properties": {"sessionType": "therapy"}, "evidence": []},
            {"id": "sit_1", "label": "Situation", "parent": None,
             "properties": {"description": "exam tomorrow",
                            "kind": "externalSituation"},
             "evidence": [1]},
            {"id": "at_1", "label": "AutomaticThought", "parent": None,
             "properties": {"content": "I will fail", "modality": "verbal"},
             "evidence": [1]},
        ],
        "edges": [
            {"type": "triggers", "from": "sit_1", "to": "at_1", "evidence": [1]},
        ],
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    nodes, edges = JsonGraphReader(str(path)).load()
    ids = {n.node_id for n in nodes}
    assert {"sit_1", "at_1"}.issubset(ids)
    preds = {e.predicate for e in edges}
    assert preds == {"triggers"}
