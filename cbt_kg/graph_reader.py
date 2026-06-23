"""Universal graph readers — emit canonical V4_flat (nodes, edges) lists.

Three implementations, all returning the same shape so Part 2's query engine
is source-agnostic:

  LiveGraphReader    — wraps a Part 1 GraphStore (only status='found' items).
  JsonGraphReader    — parses a V4_flat Stage 5 export.
  Neo4jGraphReader   — reads the :ABox model from Neo4j.
"""

from __future__ import annotations

import json
from pathlib import Path

from .interfaces import GraphEdge, GraphNode, GraphReader, GraphStore
from .ontology import PREDICATE_FROM_REL


class LiveGraphReader:

    def __init__(self, graph: GraphStore, label: str = "Live session"):
        self._graph = graph
        self._label = label

    def load(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes = [n for n in self._graph.nodes() if n.status == "found"]
        edges = [e for e in self._graph.edges() if e.status == "found"]
        return nodes, edges

    def label(self) -> str:
        return self._label


class JsonGraphReader:
    """Parses a V4_flat Stage 5 JSON export.

    Shape:
      {
        "meta": {...},
        "tbox_nodes": [...],   "tbox_edges": [...],   (ignored — class hierarchy)
        "nodes": [{"id","label","parent","properties","evidence"}, ...],
        "edges": [{"type","from","to","evidence", "reportedIntensity"?}, ...]
      }
    """

    def __init__(self, path: str):
        self._path = path

    def load(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        data = json.loads(Path(self._path).read_text(encoding="utf-8"))
        nodes_raw = data.get("nodes") or []
        edges_raw = data.get("edges") or []
        nodes: list[GraphNode] = []
        for n in nodes_raw:
            nodes.append(GraphNode(
                node_id=str(n.get("id")),
                label=str(n.get("label")),
                props=dict(n.get("properties") or {}),
                status="found",
                evidence=list(n.get("evidence") or []),
            ))
        edges: list[GraphEdge] = []
        for e in edges_raw:
            props: dict = {}
            if e.get("reportedIntensity"):
                props["reportedIntensity"] = e["reportedIntensity"]
            edges.append(GraphEdge(
                subject_id=str(e.get("from")),
                predicate=str(e.get("type")),
                object_id=str(e.get("to")),
                props=props,
                status="found",
                evidence=list(e.get("evidence") or []),
            ))
        return nodes, edges

    def label(self) -> str:
        return f"JSON: {Path(self._path).name}"


class Neo4jGraphReader:
    """Reads the V4_flat :ABox model from a Neo4j instance.

    Compatible with both:
      - Part 1's Neo4jGraphStore writes (this codebase)
      - V4_flat batch pipeline writes (cbt_stage5_persist_v4.write_neo4j)
    """

    def __init__(self, uri: str, user: str, password: str):
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def load(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        with self._driver.session() as s:
            for row in s.run(
                "MATCH (n:ABox) "
                "OPTIONAL MATCH (n)-[:EVIDENCED_BY]->(u:Utterance) "
                "RETURN n.id AS id, n.primaryLabel AS lbl, labels(n) AS labels, "
                "properties(n) AS props, collect(DISTINCT u.turnIndex) AS evs"
            ):
                lbl = row["lbl"]
                if not lbl:
                    others = [l for l in (row["labels"] or []) if l != "ABox"]
                    lbl = others[0] if others else "Unknown"
                props = {k: v for k, v in (row["props"] or {}).items()
                         if k not in ("id", "primaryLabel", "turnAcquired")}
                evs = [e for e in (row["evs"] or []) if e is not None]
                nodes.append(GraphNode(
                    node_id=row["id"], label=lbl, props=props,
                    status="found", evidence=sorted(evs),
                ))
            for row in s.run(
                "MATCH (a:ABox)-[r]->(b:ABox) "
                "RETURN a.id AS sid, b.id AS oid, type(r) AS rel, "
                "properties(r) AS props"
            ):
                pred = PREDICATE_FROM_REL.get(row["rel"])
                if not pred:
                    continue
                rp = dict(row["props"] or {})
                ev = rp.pop("evidence", []) or []
                edges.append(GraphEdge(
                    subject_id=row["sid"], predicate=pred, object_id=row["oid"],
                    props=rp, status="found", evidence=list(ev),
                ))
        return nodes, edges

    def label(self) -> str:
        return "Neo4j"
