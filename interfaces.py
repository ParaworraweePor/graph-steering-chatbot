"""Stable contract shared by every module.

`schema.py`, `graph.py`, and `extract.py` (and `generate.py`) are swappable
implementations behind the Protocols defined here. No other module may import
their concretes directly -- only `factory.py` is allowed to do that. Everyone
else (orchestrator, api, ui, prompts) depends on these interfaces only.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class OntologyField:
    key: str
    description: str
    priority: int = 1


@runtime_checkable
class Schema(Protocol):
    def fields(self) -> list[OntologyField]:
        ...

    def render(self) -> str:
        ...


@runtime_checkable
class GraphStore(Protocol):
    def apply_deltas(self, deltas: dict[str, str], turn_id: int) -> None:
        ...

    def missing(self) -> list[str]:
        ...

    def acquired_summary(self) -> str:
        ...

    def snapshot(self) -> dict:
        ...

    def reset(self) -> None:
        ...


@runtime_checkable
class Extractor(Protocol):
    def extract(self, message: str, schema_text: str) -> dict[str, str]:
        ...


@runtime_checkable
class Generator(Protocol):
    def generate(self, system: str, history: list[tuple[str, str]]) -> str:
        ...
