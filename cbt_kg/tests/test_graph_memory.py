"""Unit tests for InMemoryGraphStore — placeholders, upsert, merge, edges."""

from __future__ import annotations

from cbt_kg.graph_memory import InMemoryGraphStore
from cbt_kg.ontology import CBTSchema, NODE_CLASSES


def _store() -> InMemoryGraphStore:
    return InMemoryGraphStore(CBTSchema())


def test_reset_creates_placeholder_per_class():
    g = _store()
    labels = {n.label for n in g.nodes() if n.status == "missing"}
    expected = {c["label"] for c in NODE_CLASSES}
    assert expected.issubset(labels)


def test_upsert_flips_first_placeholder():
    g = _store()
    sit = g.upsert_node("Situation", {"description": "exam tomorrow",
                                       "kind": "externalSituation"}, 1)
    assert sit.status == "found"
    assert sit.label == "Situation"
    missing_sits = [n for n in g.nodes()
                    if n.label == "Situation" and n.status == "missing"]
    assert missing_sits == []


def test_upsert_creates_new_found_when_no_placeholder():
    g = _store()
    n1 = g.upsert_node("Situation", {"description": "exam tomorrow"}, 1)
    n2 = g.upsert_node("Situation", {"description": "fight with friend"}, 2)
    assert n1.node_id != n2.node_id
    found = [n for n in g.nodes()
             if n.label == "Situation" and n.status == "found"]
    assert len(found) == 2


def test_upsert_merges_similar_via_jaccard():
    g = _store()
    g.upsert_node("Situation", {"description": "exam tomorrow"}, 1)
    # > 60% word overlap → merges into existing node.
    g.upsert_node("Situation", {"description": "exam tomorrow morning"}, 2)
    found = [n for n in g.nodes()
             if n.label == "Situation" and n.status == "found"]
    assert len(found) == 1
    assert 1 in found[0].evidence and 2 in found[0].evidence


def test_add_edge_flips_placeholder():
    g = _store()
    sit = g.upsert_node("Situation", {"description": "exam"}, 1)
    at = g.upsert_node("AutomaticThought", {"content": "I will fail"}, 1)
    e = g.add_edge(sit.node_id, "triggers", at.node_id, evidence=[1])
    assert e.status == "found"


def test_count_found():
    g = _store()
    assert g.count_found("Problem") == 0
    g.upsert_node("Problem", {"description": "trouble sleeping",
                               "domain": "health"}, 1)
    assert g.count_found("Problem") == 1
    g.upsert_node("Problem", {"description": "work overload",
                               "domain": "work"}, 2)
    assert g.count_found("Problem") == 2


def test_apply_session_state_changes_snapshot():
    g = _store()
    g.apply_session_state("Technique", "decatastrophizing")
    snap = g.snapshot()
    assert snap["session_phase"] == "Technique"
    assert snap["active_technique"] == "decatastrophizing"


def test_cytoscape_serializes_nodes_and_edges():
    g = _store()
    g.upsert_node("Situation", {"description": "exam"}, 1)
    out = g.cytoscape()
    assert "nodes" in out and "edges" in out
    assert any(n["data"]["status"] == "found" for n in out["nodes"])
