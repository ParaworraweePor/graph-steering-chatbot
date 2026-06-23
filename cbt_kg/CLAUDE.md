# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

The runtime code lives in the `cbt_kg/` package at the repo root; this file
sits inside it (`cbt_kg/CLAUDE.md`). All commands below are run from the repo
root unless stated otherwise.

## Commands

```bash
pip install -r cbt_kg/requirements.txt
cp cbt_kg/.env.example cbt_kg/.env    # defaults: local extractor + generator (qwen3.5-nothink via Ollama)
ollama pull qwen3.5-nothink           # required for default extractor + generator

uvicorn cbt_kg.api:app --reload       # Gradio UI at / · FastAPI routes below
pytest                                # all tests; uses stub + echo (no Ollama / Neo4j needed)
pytest cbt_kg/tests/test_therapy.py::test_async_turn_returns_expected_keys   # single test
```

Offline (no Ollama): tests already default to `EXTRACTOR=stub GENERATOR=echo`
(see `cbt_kg/conftest.py`). For manual runs, set those in `cbt_kg/.env` to
bypass Ollama.

## Layout (PRD_cbt_v7.md §2)

```
graph-chatbot/             repo root
├── cbt_kg/                ← the package (all runtime code)
│   ├── ontology.py · interfaces.py · factory.py
│   ├── graph_memory.py · graph_neo4j.py · graph_reader.py
│   ├── extract.py · generate.py · prompts.py
│   ├── therapy.py · query.py
│   ├── api.py · ui.py
│   ├── tests/             (test_ontology / test_graph_memory / test_therapy / test_query)
│   ├── conftest.py · .env.example · requirements.txt · README.md · CLAUDE.md
├── V4_flat/               reference batch pipeline (ontology was ported from here)
├── PRD_cbt_v7.md          spec
└── pyproject.toml         pytest config — adds repo root to pythonpath
```

Inside `cbt_kg/`, every module uses **relative imports** (`from .ontology import …`).
Tests import via the package path (`from cbt_kg.ontology import …`). The repo
root is on `sys.path` via the `pyproject.toml` pytest config; uvicorn loads
the app as `cbt_kg.api:app`.

## Architecture (v7 — full V4_flat restructure)

Two parts, two Gradio tabs, one V4_flat ontology, one graph backend.

- **Part 1 — Therapy chatbot** (`therapy.py` + Tab 1). LLM plays therapist
  (CACTUS principles); user is the client. Every client turn runs the V4_flat
  per-turn extraction pipeline (`extract.TurnPipeline`, Tier A) against the
  client message — extract → atomize → property-classify → merge → local edges.
  Every `CONSOLIDATE_EVERY` turns, Tier B fires in a detached background task
  (session-level extract, reinforces wide-window, reframe sub-graph,
  deterministic structure).

- **Part 2 — Query chatbot** (`query.py` + Tab 2). Therapist user asks NL
  questions of any V4_flat-shaped graph: a live Part 1 session, a Stage 5 JSON
  export, or a Neo4j database. Three `GraphReader`s normalize the source into
  a canonical `list[GraphNode]` + `list[GraphEdge]`. The query engine does
  parse (LLM) → execute (deterministic Python) → answer (LLM), so retrieval is
  honest and the LLM only translates.

### The single source of truth

`ontology.py` (ported verbatim from `V4_flat/cbt_ontology_v4_flat.py`) defines
every CBT concept used anywhere: 13 node classes, property enums, glosses,
`CLASS_DEFINITIONS`, `ANCHOR_FAMILIES`, `EDGE_MAP`, `REL_TYPE`, `ID_PREFIX`,
`TEXT_PROP`, `CLASS_HIERARCHY`. **Nothing else.** The `CBTSchema` adapter at
the bottom of the file implements the `Schema` Protocol.

### The dependency rule (load-bearing)

`interfaces.py` defines six Protocols — `Schema`, `GraphStore`, `Extractor`,
`Generator`, `GraphReader` — plus `GraphNode` and `GraphEdge` dataclasses.
**Every module except `factory.py` imports only from `interfaces.py` and
`ontology.py`.** `factory.py` is the sole place that knows which class backs
each Protocol; env vars select at construction time.

### V4_flat extraction pipeline (extract.TurnPipeline)

Tier A (every client turn, background asyncio Task):

1. **EXTRACT** — V4_flat Stage 1 prompt (per-turn, ±2 context, speaker prior).
2. **ATOMIZE** — V4_flat Stage 1.2 for AutomaticThought / CoreBelief / IB only.
3. **PROPERTIES** — Stage 2.5 classifiers; discriminators first
   (`Problem.domain`, `CoreBelief.domain`, `IB.subtype`, `Reaction.channel`),
   then `distortionType`, `modality`, `Situation.kind`, `Intervention.technique`,
   `Homework.taskType`, `CoreBelief.category` (self-only), plus deterministic
   `Reaction.valence` + `Situation.temporality` from lexicons.
4. **MERGE** — string-Jaccard against existing nodes (handled inside
   `GraphStore.upsert_node`).
5. **EDGES (local)** — Stage 3 anchor prompt restricted to per-turn-safe
   predicates: `triggers`, `leadsTo`, `stemsFrom`, `manifestsAs`,
   `givesRiseTo`, `influencesPerceptionOf`, `associatedWith`. Skipped here
   (deferred to Tier B): `reinforces`, `hasAdaptiveResponse`, `produces`,
   `becomesSituation`.

Tier B (every `CONSOLIDATE_EVERY` turns, detached background task):

1. **SESSION-LEVEL** extract over the whole transcript so far
   (`CoreBelief`, `IntermediateBelief`, `Problem`, `Goal`, `Intervention`,
   `Homework`, `AdaptiveResponse`).
2. **REINFORCES** — wide-window `Reaction × CoreBelief`.
3. **REFRAME sub-graph** — `hasAdaptiveResponse` / `produces` / `appliedTo`.
4. **STRUCTURE** — deterministic `Client hasSession Session`,
   `Session hasProblem/hasIntervention/hasHomework`, `Goal targetsProblem`.

### Async turn loop (therapy.async_turn)

1. Snapshot pre-turn `cbt_context()` and `snapshot()`. Generator uses these.
2. Launch `_run_extraction` (Tier A) and `_run_generate` concurrently.
3. Await generate → `{response, technique, phase}`. Reply uses pre-turn state.
4. Await extraction. Per-session `asyncio.Lock` guards graph writes.
5. `validate_phase(...)` enforces node-class minimums from V4_flat:
   - Exploration requires `Problem` + 2 turns.
   - Technique requires `AutomaticThought` + `Situation` + 5 turns.
   - Consolidation requires `AdaptiveResponse` + 12 turns.
6. `apply_session_state(phase, technique)`.
7. If `turn_count % CONSOLIDATE_EVERY == 0`, fire Tier B as a detached task.
8. Return `{reply, technique, phase, extraction_mode, new_nodes, new_edges,
   graph_snapshot}`.

### Graph stores (graph_memory.py, graph_neo4j.py)

`InMemoryGraphStore.reset()` pre-creates one placeholder node per class plus
one placeholder edge per `(subj, pred, obj)` in the edge map. `upsert_node`
flips the first placeholder to `status='found'` on first match; further
instances create new found nodes. `add_edge` flips the matching placeholder
edge or creates a new one. Jaccard-based merging happens inside `upsert_node`.

`Neo4jGraphStore` uses the V4_flat `:ABox` model — one labeled node per
content class (label = `Problem`/`CoreBelief`/...), `primaryLabel` property,
direct property storage of `domain`/`subtype`/`channel`, `:TBox`
class-hierarchy, `EVIDENCED_BY → :Utterance`, typed edges via `REL_TYPE`.
This matches `cbt_stage5_persist_v4.write_neo4j` byte-for-byte.

### Part 2 — universal query

`GraphReader` Protocol has one method: `load() → (nodes, edges)`. Three
implementations all emit the same canonical shape — `LiveGraphReader`
(wraps a Part 1 `GraphStore`), `JsonGraphReader` (Stage 5 export),
`Neo4jGraphReader` (`:ABox` model, compatible with both Part 1 and the
V4_flat batch export). `QueryEngine.answer(question, nodes, edges)` does
parse → execute → answer; execute is deterministic Python so the LLM cannot
invent facts.

### Implementation notes worth knowing

- `LocalLLMGenerator` uses Ollama's **native `/api/chat`**, not `/v1`; always
  passes `"think": false`. `LOCAL_LLM_BASE_URL` accepts `/v1` for convenience
  but the suffix is stripped.
- `TurnPipeline` uses `/api/generate` with `format: "json"` and
  `temperature: 0`. Parse failures return `[]`; the pipeline soft-fails
  per-step (one bad prompt won't poison the whole turn).
- Sessions and loaded query-graphs are process-local dicts in `api.py`;
  restart wipes them. No persistence layer.
- `api.py` mounts Gradio **after** all FastAPI routes are defined.
- `EXTRACTION_TIMEOUT` is informational — extraction is awaited before the
  response returns. Tier B is what actually decouples from the response.
