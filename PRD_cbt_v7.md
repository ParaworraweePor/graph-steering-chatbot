# PRD: CBT Knowledge-Graph Chatbot System — v7 (Full Restructure)

**Version:** 7.0
**Status:** Ready for implementation by Claude Code
**Supersedes:** v5, v6 (this is a clean restructure, not an incremental patch)
**Model:** `qwen3.5-nothink` via Ollama native API
**Stack:** Python · FastAPI · Gradio · Ollama · Neo4j (optional) / in-memory

---

## 0. Global Rules (Read First — Non-negotiable)

1. **ONE ontology only: V4_flat.** Every CBT concept — node classes, properties,
   property enums, edge predicates, class definitions — comes from
   `cbt_ontology_v4_flat.py` / `cbt_kg_ontology_v4_flat.txt`. Nothing else.
   **Anything not in V4_flat is deleted** (see §1.3).

2. **CBT correctness is the priority.** This is a demo, but the clinical model
   must be faithful to V4_flat (which is faithful to Beck + CACTUS). Do not
   invent classes, relax enums, or simplify the cognitive model for convenience.

3. **Reuse V4_flat prompts as-is wherever possible.** The extraction prompt,
   property-classification prompts, and edge-resolution prompt already exist in
   V4_flat and are clinically tuned. Port them; do not rewrite them from memory.

4. **The dependency rule (kept from v4/v5/v6).** Only `factory.py` imports
   concrete classes. Every other module imports only from `interfaces.py`.

5. **Two parts, two tabs, one graph backend, one ontology.**
   - Part 1 = Therapy chatbot (LLM = therapist, user = client). Builds the graph.
   - Part 2 = Query chatbot (user = therapist). Reads any V4_flat-shaped graph.

---

## 1. What We're Building

### 1.1 Part 1 — Therapy Chatbot (graph builder)

A live CBT session where the **LLM plays the therapist** (CACTUS principles:
questioner, guided discovery, one question per turn) and the **user is the client**.
On every client turn, a **new per-turn extraction pipeline** updates a knowledge
graph built strictly on the V4_flat ontology. A Cytoscape.js panel shows the
graph growing live.

### 1.2 Part 2 — Query Chatbot (graph reader)

A separate tab for a **therapist user** to query session data in **natural
language**. The user types a question ("what automatic thoughts came up, and what
triggered them?"); the system answers from the graph. It is **universal**: it
reads (a) the live graph from a Part 1 session, (b) a JSON file exported by the
V4_flat batch pipeline, or (c) a Neo4j database — all sharing the V4_flat ontology.

### 1.3 What to DELETE from the current codebase

| Delete | Reason |
|---|---|
| `_CLINICAL_FIELDS` flat schema (`presenting_problem`, `negative_thought`, `cognitive_pattern`, `reframe_attempt`, `emotion`, `trigger_situation`, …) in `schema.py` | Not V4_flat ontology |
| `OntologyField`, `Schema.fields()`/`render()` flat-field machinery | Replaced by node-class ontology |
| `apply_deltas()` / flat `extract()` path in `graph.py` + `extract.py` | Replaced by node/edge pipeline |
| `ClassNode` + `PLACEHOLDER_EDGE` Neo4j model (v6) | Replaced by V4_flat `:ABox` typed-label model |
| `CBT_EXTRACTION_PROMPT` (flat-field version) in `prompts.py` | Replaced by V4_flat Stage-1 extraction prompt |
| `acquired_summary()`, priority-0 field logic | Tied to deleted flat schema |

Keep: `StubExtractor` (rename/retarget for node tests), `EchoGenerator`,
`LocalLLMGenerator`, the FastAPI/Gradio scaffolding, the dependency rule.

---

## 2. Target Project Structure

Flat, one-file-per-concern (matches the existing project style). Replaces the
current mixed layout.

```
cbt_kg/
│
├── ontology.py          # SINGLE SOURCE OF TRUTH — ported verbatim from V4_flat
│                        #   CLASS_DEFINITIONS, NODE_CLASSES, property enums/glosses,
│                        #   ANCHOR_FAMILIES, EDGE_MAP, REL_TYPE, ID_PREFIX, TEXT_PROP,
│                        #   SPEAKER_PRIOR, SUBCLASS_GLOSS, GROUP_KEY_PROP, CLASS_HIERARCHY
│
├── prompts.py           # ALL prompts:
│                        #   - V4_flat-derived: EXTRACT, ATOMIZE, PROPERTY_*, EDGE_ANCHOR,
│                        #     REINFORCES, SESSION_LEVEL
│                        #   - Therapist (CACTUS): THERAPIST_SYSTEM
│                        #   - Query: QUERY_PARSE, QUERY_ANSWER
│
├── interfaces.py        # Protocols + dataclasses (the only shared contract):
│                        #   GraphNode, GraphEdge, Schema, GraphStore, Extractor,
│                        #   Generator, GraphReader
│
├── factory.py           # ONLY file importing concretes; env-var wiring
│
├── graph_memory.py      # InMemoryGraphStore   (default)
├── graph_neo4j.py       # Neo4jGraphStore      (V4_flat :ABox model)
├── graph_reader.py      # LiveGraphReader · JsonGraphReader · Neo4jGraphReader
│
├── extract.py           # StubExtractor (tests) · TurnPipeline (Part 1 per-turn)
├── generate.py          # EchoGenerator (tests) · LocalLLMGenerator (Ollama)
│
├── therapy.py           # Part 1 orchestrator: async turn loop + phase model
├── query.py             # Part 2 NL→graph query engine
│
├── api.py               # FastAPI: /chat /reset /graph  +  /query /load_graph
├── ui.py                # Gradio: Tab 1 "Therapy" · Tab 2 "Query"
│
├── tests/
│   ├── test_ontology.py
│   ├── test_turn_pipeline.py
│   ├── test_therapy.py
│   └── test_query.py
│
├── .env.example
├── requirements.txt
├── README.md
└── CLAUDE.md
```

---

## 3. The Ontology (`ontology.py`) — Single Source of Truth

**Port `cbt_ontology_v4_flat.py` directly.** Keep all CBT content verbatim; strip
only batch-pipeline plumbing not needed at runtime (the `Turn`/`Node`/`Edge`
dataclasses for the batch pipeline can stay or be re-homed — see §5). The
following must be present and unchanged in meaning.

### 3.1 Node classes (13) and properties

| Class | Properties (enums in V4_flat) | Multi |
|---|---|---|
| `Utterance` | `text`, `speaker`(therapist\|client), `turnIndex`, `timestamp?` | yes |
| `Client` | — | no |
| `Session` | `sessionNumber?`, `sessionType`(evaluation\|therapy), `date?`, `duration?` | no |
| `Problem` | `description`, `domain`(academic\|work\|social\|family\|financial\|health\|other) | yes |
| `Goal` | `statement` | yes |
| `Intervention` | `description`, `technique`(**CACTUS-12**), `techniqueLabel?`(when technique=other) | yes |
| `Homework` | `taskDescription`, `taskType`(thoughtRecord\|behavioralExperiment\|activityScheduling\|copingCard\|skillsPractice\|reading\|other), `isOptional` | yes |
| `CoreBelief` | `content`, `domain`(self\|world\|others), `category?`(helpless\|unlovable\|worthless — **only when domain=self**) | yes |
| `IntermediateBelief` | `content`, `subtype`(attitude\|rule\|assumption) | yes |
| `Situation` | `description`, `kind`(externalSituation\|thoughtStream\|image\|emotion\|behavior\|physiological), `temporality?`(past\|present\|anticipated — **only with explicit time marker**) | yes |
| `AutomaticThought` | `content`, `modality`(verbal\|image), `distortionType?`(**PatternReframe-10**) | yes |
| `Reaction` | `content`, `channel`(emotional\|behavioral\|physiological), `valence?`(positive\|negative — **only when channel=emotional**) | yes |
| `AdaptiveResponse` | `content` | yes |

**CACTUS-12 technique enum:** `efficiencyEvaluation`, `pieChartTechnique`,
`alternativePerspective`, `decatastrophizing`, `prosAndConsAnalysis`,
`evidenceBasedQuestioning`, `realityTesting`, `continuumTechnique`,
`changingRulesToWishes`, `behaviorExperiment`, `problemSolvingSkillsTraining`,
`systematicExposure`, `other`.

**PatternReframe-10 distortionType enum:** `allOrNothing`, `catastrophizing`,
`discountingPositive`, `fortuneTelling`, `labeling`, `mentalFiltering`,
`mindReading`, `overgeneralization`, `personalization`, `shouldStatements`, `none`.

### 3.2 Edges (predicate registry)

Cognitive chain:
`CoreBelief givesRiseTo IntermediateBelief` ·
`IntermediateBelief influencesPerceptionOf Situation` ·
`Situation triggers AutomaticThought` ·
`AutomaticThought leadsTo Reaction` (edge prop `reportedIntensity?`) ·
`AutomaticThought stemsFrom CoreBelief` ·
`Reaction reinforces CoreBelief` ·
`Reaction becomesSituation Situation` ·
`AutomaticThought hasAdaptiveResponse AdaptiveResponse`.

Structure:
`Client hasSession Session` ·
`Session hasProblem Problem` · `Session hasIntervention Intervention` ·
`Session hasHomework Homework` ·
`Problem manifestsAs Situation` · `Goal targetsProblem Problem` ·
`Homework targets {Problem|AutomaticThought|IntermediateBelief|CoreBelief}`.

Cross-layer hinge:
`AutomaticThought associatedWith Problem` (fallback when no Situation) ·
`Intervention appliedTo {AutomaticThought|IntermediateBelief|CoreBelief|Problem}` ·
`Intervention produces AdaptiveResponse`.

Provenance:
`<contentNode> evidencedBy Utterance` · `Utterance inSession Session`.

Keep `ANCHOR_FAMILIES`, `REINFORCES`, `ALLOWED_SIGNATURES`, `DISJOINT_RULES`,
`REL_TYPE`, `ID_PREFIX`, `TEXT_PROP`, `GROUP_KEY_PROP`, `CLASS_HIERARCHY`
exactly as in V4_flat.

### 3.3 CBT extraction-timing rules (these constrain Part 1's pipeline)

These come straight from the V4_flat ontology comments and **must** shape the
per-turn vs. consolidation split (§4.1):

- **Per-turn safe:** `Situation`, `AutomaticThought`, `Reaction` (concrete,
  utterance-local).
- **Session-level (emerge across turns):** `CoreBelief`, `IntermediateBelief`,
  `Problem`, `Goal`, `Intervention`, `Homework`, `AdaptiveResponse`.
- **`reinforces` (Reaction→CoreBelief):** wide-window only. *Never per-turn.*
  Absence is informative.
- **`AdaptiveResponse`:** multi-turn product of reframing; extract in a wide
  window, not per-turn.
- **`becomesSituation`:** weakest grounding; only when transcript clearly shows it.
- **Keep emotions OUT of `AutomaticThought.content`** (the feeling is a `Reaction`).
- **Never extract a therapist question as an `AutomaticThought`.**
- **`Reaction.valence`** is lexicon-derived in V4_flat (Thai emotion list). For
  this demo see §4.1 note (use an English emotion lexicon or LLM with explicit
  positive/negative gloss; document the choice).

---

## 4. Part 1 — Therapy Chatbot

### 4.1 The new per-turn pipeline (`extract.py :: TurnPipeline`)

This replaces the old 4-step pipeline. It is a **two-tier** design that mirrors
V4_flat's own batch stages but runs incrementally, and it respects §3.3's timing
rules. **Every LLM step reuses a V4_flat prompt** (§4.2).

#### Tier A — Per-turn fast pass (runs every client turn, in background async task)

Called as `TurnPipeline.process_turn(client_msg, window, graph, turn_index)`:

1. **EXTRACT** — V4_flat **Stage 1** prompt (it is already per-turn: one target
   turn + ±2 context). Returns `[{label, text, group_key?}]`. Filter to
   `EXTRACT_CLASSES`. Apply `SPEAKER_PRIOR` (client turns bias to
   Situation/AT/Reaction/CoreBelief/IB/Problem/Goal).

2. **ATOMIZE** — V4_flat **Stage 1.2** prompt, batched, for
   `AutomaticThought`/`CoreBelief`/`IntermediateBelief` candidates only. Split
   multi-concept items into ≤4 atomic nodes. Fail-safe: parse error → keep original.

3. **PROPERTIES** — V4_flat **Stage 2.5** classify prompts, on the *new*
   candidates only:
   - discriminators: `Problem.domain`, `CoreBelief.domain`,
     `IntermediateBelief.subtype`, `Reaction.channel`
   - then: `AutomaticThought.distortionType` + `modality`, `Situation.kind` +
     `temporality`, `CoreBelief.category` (self only), `Reaction.valence`
     (emotional only), `Intervention.technique`, `Homework.taskType`/`isOptional`.
   - Batch by property type. Each is a small constrained-JSON call.

4. **MERGE/NORMALIZE** — lightweight per-turn analog of V4_flat **Stage 2**.
   For each new candidate, compare to existing graph nodes of the *same class*:
   string-Jaccard > 0.6 → candidate; tie-break with one batched LLM "same?" call
   only when ambiguous. Match → in-place upgrade (union evidence turns, keep the
   richer property set). No match → new node. Attach `evidencedBy → Utterance`.

5. **EDGES (local)** — V4_flat **Stage 3** `_ANCHOR_PROMPT`, subject-anchored,
   restricted to the per-turn-safe cognitive chain. For each new/updated subject
   node in `ANCHOR_FAMILIES`, gather candidate objects already in the graph and
   issue **one** anchor call covering all its predicates. Confirm:
   `triggers`, `leadsTo` (+`reportedIntensity`), `stemsFrom`,
   `manifestsAs`, `givesRiseTo`, `influencesPerceptionOf`, `associatedWith`.
   **Skip per-turn:** `reinforces`, `hasAdaptiveResponse`, `produces`,
   `becomesSituation` (deferred to Tier B).

#### Tier B — Consolidation pass (runs every `CONSOLIDATE_EVERY` turns, and on reset/session-end; background)

Mirrors the stages that V4_flat marks as session-level:

1. **SESSION-LEVEL EXTRACT** — V4_flat **Stage 1.1** prompt over the whole
   transcript so far, for `CoreBelief`, `IntermediateBelief`, `Problem`, `Goal`,
   `Intervention`, `Homework`, `AdaptiveResponse` (+ the Reaction recovery pass).
   Additive; then re-run MERGE to dedupe against Tier-A nodes.

2. **REINFORCES** — V4_flat **Stage 3 Pass B** wide-window prompt
   (Reaction × CoreBelief). Add confirmed `reinforces` edges.

3. **REFRAME SUB-GRAPH** — confirm `AutomaticThought hasAdaptiveResponse
   AdaptiveResponse` and `Intervention produces AdaptiveResponse` / `appliedTo`
   over the wide window.

4. **STRUCTURE** — deterministic edges: `Client hasSession Session`,
   `Session hasProblem/hasIntervention/hasHomework`, `Goal targetsProblem`,
   `Homework targets`.

> **Latency note:** Tier A is ~4–7 Ollama calls/turn. Because extraction runs in
> a background `asyncio.Task` (Option 1/2 from v6 — generation never waits on it),
> chat latency is unaffected. Keep `temperature=0`, `think:false`,
> `keep_alive:10m`. Tier B runs off the critical path entirely.

> **Demo fast-path (config flag `EXTRACT_FAST=1`, default off):** collapse Step 3
> into Step 1 (ask the extractor to emit `props` inline). Fewer calls, slightly
> lower fidelity. Default keeps the faithful multi-call pipeline.

### 4.2 Prompts (`prompts.py`) — port from V4_flat

Port these **verbatim** from V4_flat (parameterize the hard-coded "The text is in
Thai" line into a `{language}` slot defaulting to "English"):

- `EXTRACT_PROMPT` ← `cbt_stage1_extract_v4.PROMPT` (with `CLASS_DEFINITIONS` block,
  `GLOBAL RULES`, speaker prior, ±2 context, JSON-array output).
- `ATOMIZE_PROMPT` ← `cbt_stage1_2_atomize` (atomize + self-belief reframe clause).
- `PROPERTY_*` prompts ← `cbt_stage2_5_properties_v4` (one per property family;
  reuse `SITUATION_KINDS`, `DISTORTION_TYPES`, `SUBCLASS_GLOSS`, technique gloss).
- `EDGE_ANCHOR_PROMPT` ← `cbt_stage3_chains_v4._ANCHOR_PROMPT` (Beck canonical-edge
  guidance, evidence_turns requirement, per-relation candidate blocks).
- `REINFORCES_PROMPT` ← `cbt_stage3_chains_v4._REINFORCES_PROMPT`.
- `SESSION_LEVEL_PROMPT` ← `cbt_stage1_1_session_extract._PROMPT`.

**Therapist system prompt (`THERAPIST_SYSTEM`)** — this is the one prompt V4_flat
does *not* provide (V4_flat is an extractor, not a therapist). Use the existing
CACTUS-based prompt, **but** purge the deleted flat-field references and align
technique names to the CACTUS-12 enum. Keep: questioner-not-advisor, empathize
only with what was said, exactly one question per turn, no jargon, don't name
techniques to the client. Phase block per §4.3.

### 4.3 Phase model (`therapy.py`) — keep the hybrid, re-ground the gates

Keep the v6 hybrid (LLM proposes phase, graph enforces minimums). Since the flat
fields are deleted, **re-express the gates in terms of V4_flat node-class
presence**:

```
PHASE_ORDER = ["Rapport", "Exploration", "Technique", "Consolidation"]

PHASE_MINIMUMS = {
  "Exploration":   {"requires": ["Problem"],                       "min_turns": 2},
  "Technique":     {"requires": ["AutomaticThought", "Situation"], "min_turns": 5},
  "Consolidation": {"requires": ["AdaptiveResponse"],              "min_turns": 12},
}
```

`validate_phase(proposed, current, graph, turn_count)`: allow forward only if the
graph holds ≥1 *found* node of each required class **and** `turn_count ≥ min_turns`;
otherwise hold at `current`. (Same shape as v6 `validate_phase`, but it queries
`graph.count_found(label)` instead of flat-field `acquired`.)

### 4.4 Async turn loop (`therapy.py`)

Keep v6's structure exactly:

1. Snapshot pre-turn graph context (`graph.cbt_context()`).
2. Launch `_run_extraction` (TurnPipeline Tier A) and `_run_generate` as
   concurrent tasks.
3. Await generate → `{response, technique, phase}` (therapist reply uses pre-turn
   state, so it never blocks on extraction).
4. Await/peek extraction (Option 1 sync if it finished within
   `EXTRACTION_TIMEOUT`, else Option 2 background). Per-session `asyncio.Lock`
   guards graph writes.
5. `validate_phase(...)`; persist phase/technique as session state.
6. If `turn_count % CONSOLIDATE_EVERY == 0`: fire Tier B as a detached background
   task (does not block the response).
7. Return `{reply, technique, phase, extraction_mode, graph_snapshot}`.

### 4.5 Graph store (`graph_memory.py`, `graph_neo4j.py`)

`GraphStore` is now a **node/edge** store (no flat fields). Required methods
(see `interfaces.py`, §5.1):

`reset()`, `upsert_node(label, props, turn_index) -> GraphNode`,
`merge_into(existing_id, props, turn_index)`, `add_edge(subj_id, pred, obj_id,
props, evidence)`, `nodes()`, `edges()`, `count_found(label) -> int`,
`cbt_context() -> str`, `apply_session_state(phase, technique)`,
`snapshot() -> dict`, `cytoscape() -> {nodes, edges}`.

**Placeholder behavior (kept from v6):** on `reset()`, pre-create one placeholder
node per content class with `status="missing"`, plus placeholder edges from the
edge map with `status="missing"`. `upsert_node` flips the first instance to
`status="found"` and fills props; further instances create new found nodes.
`add_edge` flips a placeholder edge to `found` or creates a new one. The
Cytoscape panel renders missing = grey/dashed, found = colored (per-class colors).

**Neo4j model — use the V4_flat `:ABox` representation, NOT v6's `ClassNode`:**

```
(:Client:ABox {id})
(:Session:ABox {id, sessionType})
(:Problem:ABox {id, description, domain, status, primaryLabel:"Problem"})
... one labeled node per content class, props as direct properties ...
(:Utterance:ABox {id, turnIndex, speaker, text})
(content)-[:EVIDENCED_BY]->(:Utterance)
(:Utterance)-[:IN_SESSION]->(:Session)
typed edges via REL_TYPE: (a)-[:TRIGGERS]->(b), (a)-[:LEADS_TO {reportedIntensity}]->(b), ...
(:TBox {name}) class hierarchy with SUB_CLASS_OF, content (x)-[:IS_A]->(:TBox)
property indexes on discriminators (Problem.domain, CoreBelief.domain, IB.subtype, Reaction.channel)
```

This is **exactly** what `cbt_stage5_persist_v4.write_neo4j` produces, so a graph
written by Part 1 is byte-compatible with a graph from the V4_flat batch pipeline.
That compatibility is the whole point — it makes Part 2 universal.

`cbt_context()` renders a compact found-node summary grouped by class + current
phase/technique, for injection into `THERAPIST_SYSTEM`.

---

## 5. Part 2 — Query Chatbot

### 5.1 Universal ingestion (`graph_reader.py`)

A `GraphReader` Protocol returns a **canonical in-memory graph** regardless of
source. Canonical form = `list[GraphNode]` + `list[GraphEdge]` using the exact
V4_flat labels/predicates/props.

```python
class GraphReader(Protocol):
    def load(self) -> tuple[list[GraphNode], list[GraphEdge]]: ...
    def label(self) -> str: ...   # human-readable source name for the UI
```

Three implementations, all emitting identical canonical output:

- **`LiveGraphReader(graph_store)`** — wraps a running Part 1 `GraphStore`; calls
  `nodes()`/`edges()` and returns only `status=="found"` items.
- **`JsonGraphReader(path)`** — parses a V4_flat **Stage 5** export
  (`{meta, tbox_nodes, tbox_edges, nodes:[{id,label,properties,evidence}],
  edges:[{type,from,to,evidence}]}`). Maps `properties` → `props`, `type` →
  `predicate`. This is the "graph downloaded from Neo4j / exported by the
  pipeline" case.
- **`Neo4jGraphReader(uri,user,pw)`** — reads the `:ABox` model: `MATCH (n:ABox)`
  for nodes (label from `primaryLabel`/first non-ABox label, props from node
  properties), `MATCH (a:ABox)-[r]->(b:ABox)` for edges (predicate via reverse
  `REL_TYPE`). Skips `:TBox`.

Because Part 1's Neo4j store (§4.5) and V4_flat's batch export use the same model,
`Neo4jGraphReader` works for both without branching.

### 5.2 NL → graph query engine (`query.py`)

**Source-agnostic by design:** load the whole session graph into memory (it's
small — one session), then answer over it. This works for JSON dumps and live
graphs too, not just Neo4j, so we do **not** rely on text-to-Cypher.

Two-step, both using the local LLM:

1. **PARSE** (`QUERY_PARSE` prompt) — translate the therapist's NL question into a
   structured **query spec** over V4_flat vocabulary:
   ```json
   {
     "intent": "list | trace | count | describe | summarize",
     "node_labels": ["AutomaticThought", ...],
     "predicates": ["triggers", "leadsTo", ...],
     "property_filters": {"domain": "self", "distortionType": "catastrophizing"},
     "free_text": "<residual question for the answerer>"
   }
   ```
   The prompt includes the V4_flat class + predicate + enum vocabulary so the LLM
   can only select valid terms (reject/repair anything off-ontology).

2. **EXECUTE (deterministic)** — run the spec over the loaded canonical graph:
   filter nodes by label + property_filters; for `trace` intents, walk the
   cognitive chain along the requested predicates (e.g. Situation→AT→Reaction,
   AT→CoreBelief). Returns a structured result set (nodes + the edges connecting
   them + their evidence turns).

3. **ANSWER** (`QUERY_ANSWER` prompt) — feed the result set (compact, grounded,
   with node ids + evidence turn indices) to the LLM, which writes the
   therapist-facing answer. Rule in the prompt: **answer only from the provided
   result set; cite node ids / evidence turns; say "not in this session's graph"
   if empty.** No invention.

This split keeps the LLM honest (retrieval is deterministic; the LLM only
parses and narrates) and works identically across all three sources.

### 5.3 Query UI behavior

Tab 2 has: a **source selector** (Live session · Upload JSON · Neo4j connection),
a **load** action that instantiates the right `GraphReader` and caches the
canonical graph, a chat box for NL questions, and a small read-only graph preview
(reuse the Cytoscape panel, filtered to the loaded graph). The query chat is
**read-only** — it never writes to the graph.

---

## 6. Shared Infrastructure

### 6.1 `interfaces.py`

```python
@dataclass
class GraphNode:
    node_id: str
    label: str                 # V4_flat class, e.g. "AutomaticThought"
    props: dict                # V4_flat properties (content/domain/kind/...)
    status: str = "found"      # "found" | "missing"
    evidence: list[int] = field(default_factory=list)
    turn_acquired: int | None = None

@dataclass
class GraphEdge:
    subject_id: str
    predicate: str             # V4_flat predicate, e.g. "triggers"
    object_id: str
    props: dict = field(default_factory=dict)   # e.g. {"reportedIntensity": "8/10"}
    status: str = "found"
    evidence: list[int] = field(default_factory=list)
```

Protocols: `Schema` (exposes ontology: `node_classes()`, `edge_map()`,
`anchor_families()`, `class_definitions()`, `render_ontology()`),
`GraphStore` (§4.5), `Extractor` (`process_turn(...)`, `consolidate(...)`),
`Generator` (`generate(system, history) -> dict`), `GraphReader` (§5.1).

### 6.2 `factory.py`

Single import site for concretes. Env vars:
`GRAPH_BACKEND` (memory|neo4j), `EXTRACTOR` (stub|local), `GENERATOR`
(echo|local|openrouter), plus `OLLAMA_MODEL`, `OLLAMA_HOST`, `EXTRACTION_TIMEOUT`,
`CONSOLIDATE_EVERY`, `EXTRACT_FAST`. Builds a `Session` for Part 1 and a
`GraphReader` for Part 2.

### 6.3 `generate.py`

Keep `LocalLLMGenerator` (Ollama native `/api/chat`, `think:false`, returns dict
`{response, technique, phase}` with JSON-parse + fallback) and `EchoGenerator`
(dict stub) unchanged in behavior.

---

## 7. API & UI

### 7.1 `api.py` (FastAPI)

| Route | Part | Purpose |
|---|---|---|
| `POST /chat` | 1 | `{session_id, message}` → therapist reply (async turn loop) |
| `POST /reset` | 1 | reset a session graph |
| `GET /graph/{session_id}` | 1 | Cytoscape JSON of the live graph (polled every 3s) |
| `POST /load_graph` | 2 | `{source: live|json|neo4j, ...}` → instantiate GraphReader, cache canonical graph, return summary |
| `POST /query` | 2 | `{graph_handle, question}` → NL answer (parse→execute→answer) |
| `GET /graph_preview/{handle}` | 2 | Cytoscape JSON of a loaded (read-only) graph |

Sessions and loaded graphs are **process-local dicts** (restart clears them — per
your decision). No persistence layer.

### 7.2 `ui.py` (Gradio, two tabs)

- **Tab 1 — Therapy:** two columns. Left = chat (client types, therapist replies;
  show current phase + active technique under each reply). Right = live Cytoscape
  graph polling `/graph`. Node colors per class; missing = grey/dashed.
- **Tab 2 — Query:** source selector + load button; NL chat; read-only Cytoscape
  preview of the loaded graph.

Reuse one Cytoscape HTML component for both tabs (parameterized by endpoint).

---

## 8. File-by-File Implementation Spec (summary)

| File | Action | Key content |
|---|---|---|
| `ontology.py` | **Create** (port from V4_flat) | classes, props, enums, ANCHOR_FAMILIES, EDGE_MAP, REL_TYPE, CLASS_DEFINITIONS, glosses |
| `prompts.py` | **Replace** | V4_flat EXTRACT/ATOMIZE/PROPERTY/EDGE/REINFORCES/SESSION prompts + THERAPIST_SYSTEM + QUERY_PARSE/QUERY_ANSWER |
| `interfaces.py` | **Replace** | GraphNode, GraphEdge, Schema, GraphStore, Extractor, Generator, GraphReader |
| `factory.py` | **Replace** | env wiring for both parts |
| `graph_memory.py` | **Create** | InMemoryGraphStore (node/edge + placeholders) |
| `graph_neo4j.py` | **Create** | Neo4jGraphStore (V4_flat :ABox model) |
| `graph_reader.py` | **Create** | LiveGraphReader, JsonGraphReader, Neo4jGraphReader |
| `extract.py` | **Replace** | StubExtractor + TurnPipeline (Tier A + Tier B) |
| `generate.py` | **Edit** | keep generators; dict return |
| `therapy.py` | **Create** | async turn loop, validate_phase (node-grounded), consolidation trigger |
| `query.py` | **Create** | parse→execute→answer engine |
| `api.py` | **Replace** | routes in §7.1 |
| `ui.py` | **Replace** | two tabs |
| `.env.example` | **Edit** | new vars (§6.2) |
| `tests/` | **Replace** | ontology, turn pipeline, therapy, query |
| `README.md`, `CLAUDE.md` | **Edit** | document the two parts + ontology source |

---

## 9. Implementation Order (each step independently testable)

1. `ontology.py` — port + `test_ontology.py` (assert 13 classes, all enums,
   edge map, ANCHOR_FAMILIES present and matching V4_flat).
2. `interfaces.py` — dataclasses + protocols.
3. `graph_memory.py` — node/edge store + placeholders; unit test upsert/merge/edge/count_found.
4. `prompts.py` — port all prompts; assert format-slots present.
5. `extract.py` — `StubExtractor` first (deterministic, offline) →
   `test_turn_pipeline.py` against the stub. Then `TurnPipeline` Tier A, then Tier B.
6. `generate.py` — keep; ensure dict contract.
7. `therapy.py` — async turn loop + node-grounded `validate_phase`;
   `test_therapy.py` (turn returns expected keys; phase gating holds without
   required nodes; advances with them).
8. `graph_neo4j.py` — V4_flat :ABox model; parity test vs `write_neo4j` shape.
9. `graph_reader.py` — three readers; `test_query.py` loads the same canonical
   graph from live store, a JSON fixture (a real V4_flat export), and (optional)
   Neo4j; assert node/edge counts match.
10. `query.py` — parse→execute→answer; test deterministic execute over a fixture.
11. `factory.py`, `api.py`, `ui.py` — wire up both tabs.
12. `pytest` green; manual smoke: run a short session in Tab 1, watch the graph
    grow, then query it in Tab 2; separately, load a V4_flat JSON export in Tab 2
    and query it.

Run `pytest` after steps 3, 5, 7, 9 — must be green before continuing.

---

## 10. Acceptance Criteria

- Only V4_flat ontology terms appear anywhere (no `presenting_problem` etc.).
- A Part 1 session produces a graph whose JSON export is schema-identical to a
  V4_flat batch export (same node labels, property keys/enums, predicate names).
- The same `query.py` answers NL questions over (a) a live Part 1 graph and
  (b) a downloaded V4_flat JSON export, with identical phrasing of results.
- Per-turn chat latency is unaffected by extraction (extraction is background).
- Phase gating refuses to advance to `Technique` until ≥1 `AutomaticThought` and
  ≥1 `Situation` exist and ≥5 turns have passed (and the analogous gates).
- `reinforces` and `AdaptiveResponse` never appear from a single turn — only
  after a consolidation pass.

---

## 11. Deferred (do NOT implement now)

- Stage-4-style heavy edge validation (4a/4b) in the live loop — Tier B keeps a
  light validation; full validation stays batch-only.
- Embedding-based merge (use string-Jaccard + occasional LLM tie-break for now).
- Text-to-Cypher query path (the in-memory deterministic execute is universal).
- Multi-session persistence / export-to-disk (sessions restart per your decision).
- WebSocket push for the graph panel (polling is fine).
- Option B typed-subclass graph (V4_flat flat model only).

---

## 12. Running

```bash
ollama pull qwen3.5-nothink
ollama serve

# optional Neo4j (for Neo4j-backed graphs and the Neo4jGraphReader)
docker run -p7474:7474 -p7687:7687 -e NEO4J_AUTH=neo4j/changeme neo4j:5

cp .env.example .env
pip install -r requirements.txt
uvicorn api:app --reload          # http://localhost:8000/  → Tab 1 Therapy · Tab 2 Query
pytest
```
