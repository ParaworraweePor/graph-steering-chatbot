"""Swappable graph store implementations.

InMemoryGraphStore - no external dependency, used for the default demo path
and tests.
Neo4jGraphStore - the default production backend. ALL Cypher lives in this
file; no other module is allowed to know Neo4j exists.

Both implementations derive their slots from the injected Schema, never from
hardcoded field names.
"""

from interfaces import Schema


class InMemoryGraphStore:
    """In-process graph store with no DB dependency."""

    def __init__(self, schema: Schema):
        self._schema = schema
        self._fields_by_priority = sorted(schema.fields(), key=lambda f: f.priority)
        self._state: dict[str, dict] = {}
        self.reset()

    def reset(self) -> None:
        self._state = {
            f.key: {"value": None, "acquired": False, "turns": []}
            for f in self._fields_by_priority
        }

    def apply_deltas(self, deltas: dict[str, str], turn_id: int) -> None:
        for key, value in deltas.items():
            if key not in self._state:
                continue
            entry = self._state[key]
            entry["value"] = value
            entry["acquired"] = True
            entry["turns"].append(turn_id)

    def missing(self) -> list[str]:
        return [
            f.key
            for f in self._fields_by_priority
            if not self._state[f.key]["acquired"]
        ]

    def acquired_summary(self) -> str:
        acquired = [
            f"{key}={entry['value']}"
            for key, entry in self._state.items()
            if entry["acquired"]
        ]
        return ", ".join(acquired) if acquired else "(nothing acquired yet)"

    def snapshot(self) -> dict:
        return {
            key: {"value": entry["value"], "acquired": entry["acquired"]}
            for key, entry in self._state.items()
        }


class Neo4jGraphStore:
    """Neo4j-backed graph store.

    Graph model:
      (:Session {id}) -[:HAS_FIELD]-> (:Field {key, value, acquired})
      (:Turn {id}) and (:Field)-[:ACQUIRED_FROM]->(:Turn) evidence edges.
    """

    def __init__(self, schema: Schema, uri: str, user: str, password: str, session_id: str = "default"):
        from neo4j import GraphDatabase  # imported lazily; only this file knows Neo4j exists

        self._schema = schema
        self._fields_by_priority = sorted(schema.fields(), key=lambda f: f.priority)
        self._session_id = session_id
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self.reset()

    def close(self) -> None:
        self._driver.close()

    def reset(self) -> None:
        with self._driver.session() as session:
            session.run(
                "MATCH (s:Session {id: $session_id}) "
                "OPTIONAL MATCH (s)-[:HAS_FIELD]->(f:Field) "
                "OPTIONAL MATCH (f)-[:ACQUIRED_FROM]->(t:Turn) "
                "DETACH DELETE s, f, t",
                session_id=self._session_id,
            )
            session.run(
                "MERGE (s:Session {id: $session_id})",
                session_id=self._session_id,
            )
            for f in self._fields_by_priority:
                session.run(
                    """
                    MATCH (s:Session {id: $session_id})
                    MERGE (s)-[:HAS_FIELD]->(field:Field {key: $key})
                    SET field.value = null, field.acquired = false, field.priority = $priority
                    """,
                    session_id=self._session_id,
                    key=f.key,
                    priority=f.priority,
                )

    def apply_deltas(self, deltas: dict[str, str], turn_id: int) -> None:
        if not deltas:
            return
        with self._driver.session() as session:
            session.run(
                "MERGE (t:Turn {id: $turn_id})",
                turn_id=turn_id,
            )
            for key, value in deltas.items():
                session.run(
                    """
                    MATCH (s:Session {id: $session_id})-[:HAS_FIELD]->(field:Field {key: $key})
                    MATCH (t:Turn {id: $turn_id})
                    SET field.value = $value, field.acquired = true
                    MERGE (field)-[:ACQUIRED_FROM]->(t)
                    """,
                    session_id=self._session_id,
                    key=key,
                    value=value,
                    turn_id=turn_id,
                )

    def missing(self) -> list[str]:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (s:Session {id: $session_id})-[:HAS_FIELD]->(field:Field)
                WHERE field.acquired = false
                RETURN field.key AS key
                ORDER BY field.priority ASC
                """,
                session_id=self._session_id,
            )
            return [record["key"] for record in result]

    def acquired_summary(self) -> str:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (s:Session {id: $session_id})-[:HAS_FIELD]->(field:Field)
                WHERE field.acquired = true
                RETURN field.key AS key, field.value AS value
                ORDER BY field.priority ASC
                """,
                session_id=self._session_id,
            )
            acquired = [f"{record['key']}={record['value']}" for record in result]
            return ", ".join(acquired) if acquired else "(nothing acquired yet)"

    def snapshot(self) -> dict:
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (s:Session {id: $session_id})-[:HAS_FIELD]->(field:Field)
                RETURN field.key AS key, field.value AS value, field.acquired AS acquired
                ORDER BY field.priority ASC
                """,
                session_id=self._session_id,
            )
            return {
                record["key"]: {"value": record["value"], "acquired": record["acquired"]}
                for record in result
            }
