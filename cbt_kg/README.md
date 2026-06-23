# CBT Knowledge-Graph Chatbot — V4_flat

A two-tab demo of a CBT chatbot whose graph is built strictly on the V4_flat
clinical ontology. Spec: `../PRD_cbt_v7.md`.

- **Tab 1 — Therapy.** The local LLM (`qwen3.5-nothink` via Ollama) plays a
  CACTUS-style therapist (guided discovery, questioner). Every client turn
  runs the V4_flat per-turn extraction pipeline and updates a live knowledge
  graph (Cytoscape.js panel).
- **Tab 2 — Query.** A therapist user asks natural-language questions of any
  V4_flat-shaped graph: the live Part 1 session, a Stage 5 JSON export, or a
  Neo4j database — same answers from all three.

The V4_flat batch pipeline lives unmodified at the repo root in `../V4_flat/`;
its ontology was ported verbatim into `cbt_kg/ontology.py` and is the single
source of truth for the runtime code.

## Layout

```
graph-chatbot/                     repo root
├── cbt_kg/                        ← this package
│   ├── ontology.py                single source of truth (port of V4_flat/cbt_ontology_v4_flat.py)
│   ├── interfaces.py              GraphNode, GraphEdge + 5 Protocols
│   ├── factory.py                 the ONLY file that imports concretes
│   │
│   ├── graph_memory.py            InMemoryGraphStore (default)
│   ├── graph_neo4j.py             Neo4jGraphStore — V4_flat :ABox model
│   ├── graph_reader.py            Live · Json · Neo4j readers
│   │
│   ├── extract.py                 StubExtractor · TurnPipeline (Tier A + Tier B)
│   ├── generate.py                EchoGenerator · LocalLLMGenerator · OpenRouterGenerator
│   ├── prompts.py                 V4_flat extraction prompts + THERAPIST_SYSTEM + QUERY_*
│   │
│   ├── therapy.py                 Part 1 orchestrator
│   ├── query.py                   Part 2 parse → execute → answer
│   │
│   ├── api.py                     FastAPI app (mounts Gradio at /)
│   ├── ui.py                      Gradio (Tab 1: Therapy · Tab 2: Query)
│   │
│   ├── tests/                     test_ontology · test_graph_memory · test_therapy · test_query
│   ├── conftest.py                forces stub + echo + memory by default
│   ├── .env.example               copy to cbt_kg/.env to override
│   ├── requirements.txt
│   ├── README.md                  ← you are here
│   └── CLAUDE.md
│
├── V4_flat/                       reference batch pipeline (ontology was ported from here)
├── PRD_cbt_v7.md
└── pyproject.toml                 pytest config — adds repo root to pythonpath
```

The dependency rule is load-bearing: only `factory.py` imports concretes;
every other module imports from `interfaces.py` and `ontology.py` only.

## Run (zero external services)

```bash
pip install -r cbt_kg/requirements.txt
cp cbt_kg/.env.example cbt_kg/.env
# In cbt_kg/.env set:
#   EXTRACTOR=stub
#   GENERATOR=echo
uvicorn cbt_kg.api:app --reload
```

Open <http://localhost:8000/>.

## Run with the local LLM (Ollama)

```bash
ollama pull qwen3.5-nothink
ollama serve

cp cbt_kg/.env.example cbt_kg/.env    # defaults to local extractor + generator
uvicorn cbt_kg.api:app --reload
```

## Run with Neo4j

```bash
docker run -p7474:7474 -p7687:7687 -e NEO4J_AUTH=neo4j/changeme neo4j:5

# in cbt_kg/.env:
GRAPH_BACKEND=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme

uvicorn cbt_kg.api:app --reload
```

## Tests

```bash
pytest                                       # from repo root
pytest cbt_kg/tests/test_therapy.py          # single file
```

Tests run fully offline — `cbt_kg/conftest.py` forces
`EXTRACTOR=stub GENERATOR=echo GRAPH_BACKEND=memory`. Coverage:

- `tests/test_ontology.py` — asserts the V4_flat ontology is ported intact.
- `tests/test_graph_memory.py` — placeholders, upsert, Jaccard merge, edges.
- `tests/test_therapy.py` — async turn loop + node-grounded phase gates.
- `tests/test_query.py` — deterministic query executor + JSON / live readers.
