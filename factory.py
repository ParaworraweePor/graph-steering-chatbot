"""The ONLY file allowed to import concrete schema/graph/extract/generate
classes. Selection is driven by env vars. This is the swap point: replacing
an implementation means editing its file plus its one line here.
"""

import os

from dotenv import load_dotenv

from interfaces import Schema, GraphStore, Extractor, Generator
from schema import PlaceboSchema
from graph import InMemoryGraphStore, Neo4jGraphStore
from extract import StubExtractor, LocalLLMExtractor
from generate import EchoGenerator, LocalLLMGenerator, OpenRouterGenerator

load_dotenv()


def make_schema() -> Schema:
    return PlaceboSchema()


def make_graph(schema: Schema, session_id: str = "default") -> GraphStore:
    backend = os.environ.get("GRAPH_BACKEND", "memory")
    if backend == "neo4j":
        uri = os.environ["NEO4J_URI"]
        user = os.environ["NEO4J_USER"]
        password = os.environ["NEO4J_PASSWORD"]
        return Neo4jGraphStore(schema, uri, user, password, session_id=session_id)
    return InMemoryGraphStore(schema)


def make_extractor() -> Extractor:
    kind = os.environ.get("EXTRACTOR", "stub")
    if kind == "local":
        model = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        return LocalLLMExtractor(model=model, host=host)
    return StubExtractor()


def make_generator() -> Generator:
    kind = os.environ.get("GENERATOR", "echo")
    if kind == "openrouter":
        model = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
        return OpenRouterGenerator(model=model)
    if kind == "local":
        model = os.environ.get("LOCAL_LLM_MODEL", "qwen3.5:9b")
        base_url = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        return LocalLLMGenerator(model=model, base_url=base_url)
    return EchoGenerator()
