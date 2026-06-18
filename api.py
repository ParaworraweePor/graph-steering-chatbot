"""FastAPI backend. Depends only on interfaces.py and factory.py."""

from fastapi import FastAPI
from pydantic import BaseModel

import factory
from orchestrator import Session, turn

app = FastAPI(title="Therapist Chatbot Demo")

_sessions: dict[str, Session] = {}


def _get_or_create_session(session_id: str) -> Session:
    if session_id not in _sessions:
        schema = factory.make_schema()
        _sessions[session_id] = Session(
            schema=schema,
            graph=factory.make_graph(schema, session_id=session_id),
            extractor=factory.make_extractor(),
            generator=factory.make_generator(),
        )
    return _sessions[session_id]


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    deltas: dict[str, str]
    slots: dict


class ResetRequest(BaseModel):
    session_id: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    session = _get_or_create_session(request.session_id)
    result = turn(session, request.message)
    return ChatResponse(**result)


@app.post("/reset")
def reset(request: ResetRequest) -> dict:
    session = _sessions.get(request.session_id)
    if session is not None:
        session.graph.reset()
        session.history.clear()
        session.turn_count = 0
    return {"ok": True}


import gradio as gr  # noqa: E402  (mounted after routes are defined)
import ui  # noqa: E402

app = gr.mount_gradio_app(
    app,
    ui.demo,
    path="/",
    theme=gr.themes.Default(primary_hue="blue", neutral_hue="slate"),
)
