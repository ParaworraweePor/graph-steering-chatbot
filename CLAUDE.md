# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env              # offline defaults: memory graph + stub extractor + echo generator
uvicorn api:app --reload          # serves Gradio UI at / and FastAPI at /chat, /reset
pytest                            # all tests; no external services needed
pytest tests/test_orchestrator.py::test_turn_fills_graph_and_shrinks_missing  # single test
```

Backend selection is env-driven (see `.env.example`): `GRAPH_BACKEND` (memory|neo4j), `EXTRACTOR` (stub|local), `GENERATOR` (echo|openrouter|local). The defaults all run with no DB, no API keys, no Ollama.

## Architecture

This is a placebo demo of a graph-backed intake chatbot. The ontology fields (`name`, `emotion`, `placeholder_a/b/c`) and all prompt content are inert — the point of the codebase is the **swap architecture**, not the conversational content. A real ontology drops into `schema.py` (and real prompts into `prompts.py`) without touching anything else.

### The dependency rule (load-bearing)

`interfaces.py` defines four `Protocol`s — `Schema`, `GraphStore`, `Extractor`, `Generator` — plus the `OntologyField` dataclass. **Every module except `factory.py` may import only from `interfaces.py`**, never from the concretes (`schema.py`, `graph.py`, `extract.py`, `generate.py`). `factory.py` is the single place that knows which implementation backs each protocol; env vars select at construction time.

Practical consequence: swapping (e.g.) the graph backend means editing `graph.py` and the one branch in `factory.make_graph`. `orchestrator.py`, `api.py`, and `ui.py` do not change. If you find yourself needing to import `Neo4jGraphStore` or `LocalLLMExtractor` outside `factory.py`, you're breaking the contract.

### The turn loop

`orchestrator.turn(session, user_message)` is the entire app logic:

1. `extractor.extract(message, schema_text)` → `{field_key: value}` deltas
2. `graph.apply_deltas(deltas, turn_id)` → persists acquired fields
3. `graph.missing()` → fields still unfilled, in priority order
4. `prompts.GENERATION_TEMPLATE.format(...)` builds the system prompt with the ontology, acquired summary, and missing list
5. `generator.generate(system, history)` → assistant reply

The graph drives turn-taking: which field gets asked about next is a deterministic function of `missing()` + priority, not a model decision. The model's job is to phrase the next question warmly.

### Implementation notes worth knowing

- `graph.py` holds *all* Cypher. Both `InMemoryGraphStore` and `Neo4jGraphStore` derive their slot set from the injected `Schema` — never hardcode field keys in graph code. The Neo4j model is `(:Session)-[:HAS_FIELD]->(:Field)` with `(:Field)-[:ACQUIRED_FROM]->(:Turn)` evidence edges; sessions are scoped by `session_id`.
- `LocalLLMGenerator` deliberately hits Ollama's **native `/api/chat`**, not the OpenAI-compatible `/v1` endpoint. Thinking models like `qwen3.5` only reliably honor `"think": false` on the native API; on `/v1` they can stall or return empty content. The `LOCAL_LLM_BASE_URL` env var is accepted with the `/v1` suffix for convenience but the suffix is stripped internally.
- `LocalLLMExtractor` uses `/api/generate` with `format: "json"` and filters returned keys against the schema (anything unknown is dropped). `StubExtractor` looks for literal `key: value` lines and is what the tests rely on.
- Sessions are kept in a process-local `dict` in `api.py`. There is no persistence layer beyond what `Neo4jGraphStore` writes; restarting the server loses chat history.
- `api.py` mounts the Gradio app onto the FastAPI app via `gr.mount_gradio_app` — both share the same process and port. The mount call must come *after* the FastAPI routes are defined.
