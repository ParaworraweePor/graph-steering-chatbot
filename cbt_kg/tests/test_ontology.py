"""Verifies the ported V4_flat ontology matches the spec in §3 of PRD_cbt_v7."""

from __future__ import annotations

from cbt_kg.ontology import (ANCHOR_FAMILIES, CBTSchema, CLASS_DEFINITIONS,
                              CONTENT_LABELS, CORE_BELIEF_DOMAINS, DISTORTION_TYPES,
                              EDGE_MAP, EXTRACT_CLASSES, IB_SUBTYPES, NODE_CLASSES,
                              PREDICATE_FROM_REL, PROBLEM_DOMAINS, REACTION_CHANNELS,
                              REL_TYPE, SUBJECT_EDGES, TECHNIQUES, TEXT_PROP)


def test_thirteen_node_classes():
    labels = {c["label"] for c in NODE_CLASSES}
    expected = {"Utterance", "Client", "Session", "Problem", "Goal", "Intervention",
                "Homework", "CoreBelief", "IntermediateBelief", "Situation",
                "AutomaticThought", "Reaction", "AdaptiveResponse"}
    assert labels == expected, labels


def test_ten_extract_classes():
    assert set(EXTRACT_CLASSES) == {
        "Problem", "Goal", "Intervention", "Homework",
        "CoreBelief", "IntermediateBelief", "Situation",
        "AutomaticThought", "Reaction", "AdaptiveResponse",
    }


def test_class_definitions_cover_every_extract_class():
    for c in EXTRACT_CLASSES:
        assert c in CLASS_DEFINITIONS and CLASS_DEFINITIONS[c]


def test_enums_have_expected_cardinality():
    assert len(PROBLEM_DOMAINS) == 7
    assert set(CORE_BELIEF_DOMAINS) == {"self", "world", "others"}
    assert set(IB_SUBTYPES) == {"attitude", "rule", "assumption"}
    assert set(REACTION_CHANNELS) == {"emotional", "behavioral", "physiological"}
    assert len(TECHNIQUES) == 13                # CACTUS-12 + 'other'
    assert len(DISTORTION_TYPES) == 11          # PatternReframe-10 + 'none'


def test_anchor_families_cover_canonical_chain():
    # Spec §3.2: required subject→predicate→object tuples.
    expected = {
        ("Situation", "triggers", "AutomaticThought"),
        ("AutomaticThought", "leadsTo", "Reaction"),
        ("AutomaticThought", "stemsFrom", "CoreBelief"),
        ("AutomaticThought", "associatedWith", "Problem"),
        ("AutomaticThought", "hasAdaptiveResponse", "AdaptiveResponse"),
        ("CoreBelief", "givesRiseTo", "IntermediateBelief"),
        ("IntermediateBelief", "influencesPerceptionOf", "Situation"),
        ("Reaction", "becomesSituation", "Situation"),
        ("Problem", "manifestsAs", "Situation"),
        ("Goal", "targetsProblem", "Problem"),
        ("Intervention", "produces", "AdaptiveResponse"),
    }
    actual = {
        (subj, pred, obj)
        for subj, fams in ANCHOR_FAMILIES.items()
        for (pred, obj, _h) in fams
    }
    missing = expected - actual
    assert not missing, f"anchor families missing tuples: {missing}"


def test_edge_map_has_reinforces_and_structure():
    triples = set(EDGE_MAP)
    assert ("Reaction", "reinforces", "CoreBelief") in triples
    assert ("Client", "hasSession", "Session") in triples
    assert ("Session", "hasProblem", "Problem") in triples
    assert ("Session", "hasIntervention", "Intervention") in triples
    assert ("Session", "hasHomework", "Homework") in triples
    assert ("Goal", "targetsProblem", "Problem") in triples
    assert ("Utterance", "inSession", "Session") in triples
    # Evidence edges for every content class.
    for cls in CONTENT_LABELS:
        assert (cls, "evidencedBy", "Utterance") in triples


def test_rel_type_round_trips():
    for pred, rel in REL_TYPE.items():
        assert PREDICATE_FROM_REL[rel] == pred


def test_text_prop_covers_every_content_label():
    for label in CONTENT_LABELS:
        assert label in TEXT_PROP


def test_schema_protocol_methods():
    s = CBTSchema()
    assert s.node_classes() is NODE_CLASSES
    assert s.edge_map() is EDGE_MAP
    assert s.subject_edges() is SUBJECT_EDGES
    assert s.anchor_families() is ANCHOR_FAMILIES
    rendered = s.render_ontology()
    assert "AutomaticThought" in rendered
    assert "Client" not in rendered      # scaffolding classes skipped
