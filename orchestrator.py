"""The turn loop. Depends only on interfaces.py -- never on concrete
schema/graph/extract/generate implementations.
"""

from dataclasses import dataclass, field

from interfaces import Extractor, GraphStore, Generator, Schema
from prompts import GENERATION_TEMPLATE


@dataclass
class Session:
    schema: Schema
    graph: GraphStore
    extractor: Extractor
    generator: Generator
    history: list[tuple[str, str]] = field(default_factory=list)
    turn_count: int = 0


def turn(session: Session, user_message: str) -> dict:
    """Run one turn: extract -> apply_deltas -> retrieve missing -> generate.

    Returns {"reply": str, "deltas": dict, "slots": dict}.
    """
    session.turn_count += 1
    schema_text = session.schema.render()

    deltas = session.extractor.extract(user_message, schema_text)
    session.graph.apply_deltas(deltas, session.turn_count)

    missing = session.graph.missing()
    acquired_summary = session.graph.acquired_summary()

    system_prompt = GENERATION_TEMPLATE.format(
        ontology_schema=schema_text,
        acquired_summary=acquired_summary,
        missing_fields=", ".join(missing) if missing else "(none -- all acquired)",
    )

    session.history.append((user_message, ""))
    reply = session.generator.generate(system_prompt, session.history)
    session.history[-1] = (user_message, reply)

    return {
        "reply": reply,
        "deltas": deltas,
        "slots": session.graph.snapshot(),
    }
