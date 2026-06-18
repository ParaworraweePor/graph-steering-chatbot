"""Swappable ontology definition. RESERVED: a real fixed ontology drops in here
later, replacing PlaceboSchema, without touching any other file.
"""

from interfaces import OntologyField

_PLACEHOLDER_FIELDS = [
    OntologyField(key="name", description="The person's name.", priority=1),
    OntologyField(key="emotion", description="The person's current emotion.", priority=2),
    OntologyField(key="placeholder_a", description="A placeholder field A.", priority=3),
    OntologyField(key="placeholder_b", description="A placeholder field B.", priority=4),
    OntologyField(key="placeholder_c", description="A placeholder field C.", priority=5),
]


class PlaceboSchema:
    """Placebo ontology: a few inert placeholder fields, no clinical content."""

    def fields(self) -> list[OntologyField]:
        return list(_PLACEHOLDER_FIELDS)

    def render(self) -> str:
        lines = [f"- {f.key} (priority {f.priority}): {f.description}" for f in self.fields()]
        return "\n".join(lines)
