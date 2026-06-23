"""Gradio UI — two tabs: Therapy (Part 1) and Query (Part 2)."""

from __future__ import annotations

import html
import json
import os
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import gradio as gr

from . import factory
from .graph_memory import cytoscape_render
from .therapy import Session, turn

CYTOSCAPE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"

NODE_STYLES = json.dumps([
    {"selector": 'node[type="session"]',
     "style": {"background-color": "#2d6a4f", "color": "#fff",
                "label": "data(label)", "text-wrap": "wrap",
                "text-valign": "center", "font-size": "11px",
                "width": 80, "height": 80, "shape": "ellipse"}},
    {"selector": 'node[type="session_structure"]',
     "style": {"background-color": "#74c69d", "label": "data(label)",
                "text-wrap": "wrap", "text-valign": "center", "font-size": "10px",
                "width": 70, "height": 70, "shape": "round-rectangle"}},
    {"selector": 'node[type="cognitive"]',
     "style": {"background-color": "#9b72cf", "color": "#fff",
                "label": "data(label)", "text-wrap": "wrap",
                "text-valign": "center", "font-size": "10px",
                "width": 70, "height": 70, "shape": "ellipse"}},
    {"selector": 'node[type="provenance"]',
     "style": {"background-color": "#6c757d", "color": "#fff",
                "label": "data(label)", "text-wrap": "wrap",
                "text-valign": "center", "font-size": "10px",
                "width": 60, "height": 60, "shape": "tag"}},
    {"selector": 'node[type="missing"]',
     "style": {"background-color": "#dee2e6", "label": "data(label)",
                "text-valign": "center", "font-size": "9px",
                "width": 50, "height": 50,
                "border-style": "dashed", "border-color": "#adb5bd", "border-width": 2}},
    {"selector": 'edge[status="found"]',
     "style": {"label": "data(label)", "font-size": "8px", "curve-style": "bezier",
                "target-arrow-shape": "triangle", "line-color": "#74c69d",
                "target-arrow-color": "#74c69d", "arrow-scale": 0.7}},
    {"selector": 'edge[status="missing"]',
     "style": {"curve-style": "bezier", "target-arrow-shape": "triangle",
                "line-color": "#dee2e6", "target-arrow-color": "#dee2e6",
                "line-style": "dashed", "arrow-scale": 0.5}},
])

INTRO = (
    "Hello, and welcome. I'm glad you're here today. "
    "This is a safe space to talk about whatever is on your mind. "
    "What's been weighing on you lately, or what would you most like to explore today?"
)


# ─────────────────────────────────────────────────────────────────────────
# Cytoscape renderer (shared by both tabs)
# ─────────────────────────────────────────────────────────────────────────

def _render_cyto(elements: dict, height: int = 470) -> str:
    elements_json = json.dumps((elements.get("nodes") or []) + (elements.get("edges") or []))
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
<script src="{CYTOSCAPE_CDN}"></script>
</head>
<body style="margin:0; padding:0; background:#fafafa;">
<div id="cy" style="width:100%;height:{height}px;background:#fafafa;
     border:1px solid #dee2e6;border-radius:8px;box-sizing:border-box;"></div>
<script>
(function() {{
  function init() {{
    var el = document.getElementById('cy');
    if (!el || typeof cytoscape === 'undefined') {{
      setTimeout(init, 100); return;
    }}
    el.innerHTML = '';
    cytoscape({{
      container: el,
      style: {NODE_STYLES},
      layout: {{ name: 'cose', animate: false, randomize: false, nodeRepulsion: 8000 }},
      elements: {elements_json}
    }}).fit(undefined, 20);
  }}
  init();
}})();
</script>
</body>
</html>
"""
    escaped = html.escape(html_content)
    return (f'<iframe srcdoc="{escaped}" '
            f'style="width:100%; height:{height + 10}px; border:none; '
            f'border-radius:8px;"></iframe>')


# ─────────────────────────────────────────────────────────────────────────
# Tab 1 — Therapy (Part 1)
# ─────────────────────────────────────────────────────────────────────────

def _new_session() -> Session:
    schema = factory.make_schema()
    return Session(
        schema=schema,
        graph=factory.make_graph(schema),
        extractor=factory.make_extractor(),
        generator=factory.make_generator(),
    )


def _add_user(message: str, history: list):
    return history + [{"role": "user", "content": message}], "", message


def _bot_respond(message: str, history: list, session: Session):
    if session is None:
        session = _new_session()
    result = turn(session, message)
    history = history + [{"role": "assistant", "content": result["reply"]}]
    graph_html = _render_cyto(session.graph.cytoscape())
    return history, session, result["phase"], result["technique"], graph_html


def _reset_therapy():
    session = _new_session()
    history = [{"role": "assistant", "content": INTRO}]
    graph_html = _render_cyto(session.graph.cytoscape())
    return history, session, "Rapport", "Rapport Building", graph_html


# ─────────────────────────────────────────────────────────────────────────
# Tab 2 — Query (Part 2)
# ─────────────────────────────────────────────────────────────────────────

# Loaded canonical graphs keyed by handle (process-local).
_loaded_graphs: dict = {}


def _summary_text(nodes, edges, label: str) -> str:
    counts: dict[str, int] = {}
    for n in nodes:
        counts[n.label] = counts.get(n.label, 0) + 1
    rows = [f"- {k}: {v}" for k, v in sorted(counts.items())]
    return (f"Loaded **{label}** — {len(nodes)} nodes, {len(edges)} edges.\n\n"
            + ("\n".join(rows) if rows else "(empty)"))


def _load_live(therapy_session: Session):
    if therapy_session is None:
        return None, "No active therapy session yet — go to Tab 1 first.", "", "", ""
    reader = factory.make_reader_live(therapy_session.graph,
                                       label="Live therapy session")
    nodes, edges = reader.load()
    handle = uuid.uuid4().hex[:12]
    _loaded_graphs[handle] = (nodes, edges, reader.label())
    return (
        handle,
        _summary_text(nodes, edges, reader.label()),
        _render_cyto(cytoscape_render(nodes, edges)),
        "",     # clear chat
        "",     # clear input
    )


def _load_json(file_obj):
    if file_obj is None:
        return None, "Upload a V4_flat JSON export first.", "", "", ""
    path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
    reader = factory.make_reader_json(path)
    nodes, edges = reader.load()
    handle = uuid.uuid4().hex[:12]
    _loaded_graphs[handle] = (nodes, edges, reader.label())
    return (
        handle,
        _summary_text(nodes, edges, reader.label()),
        _render_cyto(cytoscape_render(nodes, edges)),
        "",
        "",
    )


def _load_neo4j(uri: str, user: str, password: str):
    try:
        reader = factory.make_reader_neo4j(
            uri=uri or os.environ.get("NEO4J_URI"),
            user=user or os.environ.get("NEO4J_USER"),
            password=password or os.environ.get("NEO4J_PASSWORD"),
        )
        nodes, edges = reader.load()
    except Exception as exc:
        return None, f"Connect failed: {exc}", "", "", ""
    handle = uuid.uuid4().hex[:12]
    _loaded_graphs[handle] = (nodes, edges, reader.label())
    return (
        handle,
        _summary_text(nodes, edges, reader.label()),
        _render_cyto(cytoscape_render(nodes, edges)),
        "",
        "",
    )


def _query_ask(handle: str, question: str, chat_history: list):
    if not handle or handle not in _loaded_graphs:
        return chat_history, "Load a graph first."
    nodes, edges, _ = _loaded_graphs[handle]
    engine = factory.make_query_engine()
    try:
        result = engine.answer(question, nodes, edges)
        answer = result.get("answer", "(no answer)")
    except Exception as exc:
        answer = f"Query failed: {exc}"
    chat_history = chat_history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    return chat_history, ""


# ─────────────────────────────────────────────────────────────────────────
# Compose the UI
# ─────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="CBT V4_flat — Therapy + Query", fill_height=True) as demo:
    session_state = gr.State(None)
    pending_msg = gr.State("")

    with gr.Tabs():
        # ── Tab 1: Therapy ───────────────────────────────────────────
        with gr.Tab("Therapy (Part 1)"):
            with gr.Row(equal_height=True):
                with gr.Column(scale=3):
                    gr.Markdown("## CBT therapy — V4_flat graph builder")
                    with gr.Row():
                        phase_box = gr.Textbox(label="Phase", value="Rapport",
                                                interactive=False, scale=1)
                        technique_box = gr.Textbox(label="Technique",
                                                     value="Rapport Building",
                                                     interactive=False, scale=3)
                    chatbot = gr.Chatbot(height=400)
                    with gr.Row():
                        msg_box = gr.Textbox(placeholder="Share what's on your mind…",
                                              show_label=False, scale=5)
                        send_btn = gr.Button("Send", variant="primary", scale=1)
                    reset_btn = gr.Button("New session")

                with gr.Column(scale=2):
                    gr.Markdown("## Knowledge graph (live)")
                    graph_panel = gr.HTML()

            therapy_outputs = [chatbot, session_state, phase_box, technique_box, graph_panel]

            send_btn.click(
                _add_user, [msg_box, chatbot], [chatbot, msg_box, pending_msg]
            ).then(
                _bot_respond, [pending_msg, chatbot, session_state], therapy_outputs
            )
            msg_box.submit(
                _add_user, [msg_box, chatbot], [chatbot, msg_box, pending_msg]
            ).then(
                _bot_respond, [pending_msg, chatbot, session_state], therapy_outputs
            )
            reset_btn.click(_reset_therapy, [], therapy_outputs)
            demo.load(_reset_therapy, [], therapy_outputs)

        # ── Tab 2: Query ────────────────────────────────────────────
        with gr.Tab("Query (Part 2)"):
            gr.Markdown("## Query a V4_flat session graph in natural language")
            handle_state = gr.State(None)

            with gr.Row():
                with gr.Column(scale=2):
                    gr.Markdown("### 1. Load a graph")
                    with gr.Tabs():
                        with gr.Tab("Live session"):
                            live_btn = gr.Button("Load current therapy session")
                        with gr.Tab("Upload JSON"):
                            json_file = gr.File(label="V4_flat Stage 5 export",
                                                  file_types=[".json"])
                            json_btn = gr.Button("Load JSON")
                        with gr.Tab("Neo4j"):
                            neo_uri = gr.Textbox(label="URI",
                                                   placeholder="bolt://localhost:7687")
                            neo_user = gr.Textbox(label="User", value="neo4j")
                            neo_pw = gr.Textbox(label="Password", type="password")
                            neo_btn = gr.Button("Connect & load")
                    summary_md = gr.Markdown("_Load a graph to start._")

                with gr.Column(scale=3):
                    gr.Markdown("### 2. Ask")
                    query_chat = gr.Chatbot(height=400)
                    with gr.Row():
                        question_box = gr.Textbox(
                            placeholder="e.g. What automatic thoughts came up and what triggered them?",
                            show_label=False, scale=5,
                        )
                        ask_btn = gr.Button("Ask", variant="primary", scale=1)

            gr.Markdown("### Loaded graph")
            query_graph_panel = gr.HTML()

            live_btn.click(
                _load_live, [session_state],
                [handle_state, summary_md, query_graph_panel, query_chat, question_box],
            )
            json_btn.click(
                _load_json, [json_file],
                [handle_state, summary_md, query_graph_panel, query_chat, question_box],
            )
            neo_btn.click(
                _load_neo4j, [neo_uri, neo_user, neo_pw],
                [handle_state, summary_md, query_graph_panel, query_chat, question_box],
            )

            ask_btn.click(
                _query_ask, [handle_state, question_box, query_chat],
                [query_chat, question_box],
            )
            question_box.submit(
                _query_ask, [handle_state, question_box, query_chat],
                [query_chat, question_box],
            )
